import re
import os
from pypdf import PdfReader
import pandas as pd
import io

def extract_latam_data(arquivo_pdf):
    # --- Helper Functions (Mantidas do original) ---
    def gerar_bilhete(documento):
        if "-" in documento:
            partes = documento.split("-")
            if len(partes) == 3:
                return re.sub(r'\D', '', partes[0] + partes[1])
            else:
                return re.sub(r'\D', '', ''.join(partes[:-1]))
        else:
            return "957000" + re.sub(r'\D', '', documento)

    def formatar_valor(valor):
        try:
            valor = str(valor).strip()
            # Remove caracteres que não são dígitos, vírgula, ponto ou sinal negativo
            # Ajuste para pypdf: às vezes vem sujeira
            valor_corrigido = valor.replace(",", "")
            # Assume que o formato no PDF é 1.234,56 ou 1234.56
            # Se pypdf quebrar tokens, pode vir diferente
            
            # Tenta limpar caracteres estranhos
            valor_corrigido = re.sub(r'[^\d\.\-]', '', valor_corrigido)
            
            if not valor_corrigido:
                return "0"

            num = float(valor_corrigido)
            formatado = f"{abs(num):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"-{formatado}" if num < 0 else formatado
        except:
            return "0"

    # --- Configurações ---
    colunas_padrao = [
        "Data", "Documento", "Vl. Tarifa", "Vl.Tx.Emb.", "Vl.Multa",
        "Vl.Rep. Terc.", "Tx.Adm", "Vl.Comissão", "Vl.Incentivo",
        "Vl.Desc", "Vl.Item Fatura", "OBS", "Bilhete"
    ]

    # Mapeamento de termos encontrados no PDF para nossas colunas internas
    mapeamento_termos = {
        "Vl. Tarifa": "Vl. Tarifa",
        "Vl.Tx.Emb.": "Vl.Tx.Emb.",
        "Vl.Multa": "Vl.Multa",
        "Vl.Rep. Terc.": "Vl.Rep. Terc.",
        "Tx.Adm": "Tx.Adm",
        "Vl.Comis.": "Vl.Comissão",
        "Vl.Comis": "Vl.Comissão",
        "Vl.Comissão": "Vl.Comissão",
        "Vl.Incent.": "Vl.Incentivo",
        "Vl.Incentivo.": "Vl.Incentivo",
        "Vl.Incentivo": "Vl.Incentivo",
        "Vl.Desc": "Vl.Desc",
        "Vl.Item Fatura": "Vl.Item Fatura",
        "Vl.Item Fat.": "Vl.Item Fatura",
    }

    colunas_numericas = colunas_padrao[2:11]

    linhas_invalidas = [
        "Venda Propria Matriz", "Ponto de Venda", "Pontos de Venda Matriz",
        "Total Tipo Item", "Total Ponto de Venda", "Total Pontos de Venda",
        "Total Fature", "Descrição", "Total Venda", "Total Fatura",
        "TAM LINHAS AEREAS", "DEMONSTRATIVO DE VENDAS"
    ]

    # --- Lógica de Extração com pypdf ---
    dados = []
    obs_atual = ""
    current_mapping = [] # Lista das colunas numéricas detectadas na página atual
    
    if not arquivo_pdf:
        return pd.DataFrame(columns=colunas_padrao)

    reader = PdfReader(arquivo_pdf)
    total_pages = len(reader.pages)
    
    for page_num, page in enumerate(reader.pages):
        try:
            text = page.extract_text(extraction_mode="layout")
        except:
            text = page.extract_text()

        if not text:
            continue
            
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 1. Detecção de Cabeçalho (Muda o mapeamento para as próximas linhas)
            # Ex típico: Data Documento Vl. Tarifa Vl.Tx.Emb. ...
            if "DATA" in line.upper() and ("DOCUMENTO" in line.upper() or "BILHETE" in line.upper()):
                current_mapping = []
                positions_found = [] # Para evitar pegar o mesmo lugar duas vezes
                
                # Ordenamos os termos do maior para o menor para evitar que "Vl.Comis" pegue o lugar de "Vl.Comissão"
                termos_ordenados = sorted(mapeamento_termos.keys(), key=len, reverse=True)
                
                for termo in termos_ordenados:
                    start_pos = 0
                    while True:
                        pos = line.upper().find(termo.upper(), start_pos)
                        if pos == -1:
                            break
                        
                        # Verifica se essa posição já foi "ocupada" por um termo mais longo
                        overlap = False
                        for pf_start, pf_end in positions_found:
                            if not (pos + len(termo) <= pf_start or pos >= pf_end):
                                overlap = True
                                break
                        
                        if not overlap:
                            current_mapping.append((pos, mapeamento_termos[termo]))
                            positions_found.append((pos, pos + len(termo)))
                        
                        start_pos = pos + 1
                
                # Ordena as colunas pela posição horizontal na linha
                current_mapping.sort()
                current_mapping = [item[1] for item in current_mapping]
                continue

            # 2. Filtro de linhas inválidas
            if any(padrao.upper() in line.upper() for padrao in linhas_invalidas):
                continue

            # 3. Captura de OBS (Tipo Item)
            if "Tipo Item:" in line:
                match_obs = re.search(r"Tipo Item:\s*(.+)", line, re.IGNORECASE)
                if match_obs:
                    obs_atual = match_obs.group(1).strip()
                continue

            # 4. Captura de Linha de Dados (Inicia com Data)
            match_data = re.match(r"^(\d{2}/\d{2}/\d{4})\s+(.+)", line)
            if match_data:
                data = match_data.group(1)
                resto = match_data.group(2)
                
                # Tenta extrair o Documento (primeira palavra após a data)
                match_doc = re.match(r"^([^\s]+)\s+(.+)", resto)
                if match_doc:
                    documento = match_doc.group(1)
                    valores_str = match_doc.group(2)
                    
                    # Extração de todos os números na linha
                    partes = valores_str.split()
                    valores_encontrados = []
                    for p in partes:
                        p_limpo = p.replace('R$', '').replace('BRL', '').replace(' ', '')
                        if re.match(r'^-?[\d,.]+$', p_limpo):
                             valores_encontrados.append(p_limpo)

                    # Cria o registro base com zeros
                    registro = {col: "0" for col in colunas_padrao}
                    registro["Data"] = data
                    registro["Documento"] = documento
                    registro["OBS"] = obs_atual
                    registro["Bilhete"] = gerar_bilhete(documento)

                    # Mapeia valores encontrados para as colunas detectadas no cabeçalho
                    # Se não detectou cabeçalho nesta página, usa o padrão das colunas numéricas
                    mapping_final = current_mapping if current_mapping else colunas_numericas
                    
                    for i, col in enumerate(mapping_final):
                        if i < len(valores_encontrados):
                            registro[col] = formatar_valor(valores_encontrados[i])
                            
                    dados.append(registro)

    # Cria DataFrame final
    df = pd.DataFrame(dados, columns=colunas_padrao)
    
    # Normalização final (garante "0" em vez de nulos ou vazios nas numéricas)
    for col in colunas_numericas:
        if col in df.columns:
            df[col] = df[col].fillna("0").replace("", "0")
            
    print(f"DEBUG: Total de registros extraídos (Latam): {len(df)}")
    return df

def criar_interface():
    janela = Tk()
    janela.title("Extrator LATAM PDF")
    janela.geometry("900x650")

    status = StringVar()
    status.set("Aguardando seleção de arquivo...")

    status_pagina = StringVar()
    status_pagina.set("")

    preview_frame = Frame(janela)
    preview_frame.pack(pady=10)

    tabela_preview = None
    df_final = None
    nome_arquivo_pdf = ""

    def selecionar_pdf():
        nonlocal df_final, nome_arquivo_pdf
        btn_selecionar.config(state="disabled")
        status.set("⏳ Lendo PDF...")
        status_pagina.set("")
        janela.update_idletasks()

        arquivo_pdf = filedialog.askopenfilename(
            title="Selecione o PDF",
            filetypes=[("PDF files", "*.pdf")]
        )

        if not arquivo_pdf:
            status.set("❌ Nenhum arquivo selecionado.")
            btn_selecionar.config(state="normal")
            return

        nome_arquivo_pdf = os.path.splitext(os.path.basename(arquivo_pdf))[0]
        
        try:
            df = extract_latam_data(arquivo_pdf)
            df_final = df
            exibir_preview(df)
            status.set("✅ Processamento concluído. Pronto para salvar.")
            btn_selecionar.config(state="normal")
        except Exception as e:
            status.set(f"❌ Erro: {e}")
            btn_selecionar.config(state="normal")

# Logic extracted to extract_latam_data function above.
