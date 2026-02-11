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

    # --- Configurações (Mantidas do original) ---
    mapeamento_colunas = {
        "Vl.Item Fat.": "Vl.Item Fatura",
        "Vl.Incent.": "Vl.Incentivo",
        "Vl.Incentivo.": "Vl.Incentivo",
        "Vl.Comis.": "Vl.Comissão",
        "Vl.Comis": "Vl.Comissão",
    }

    colunas_padrao = [
        "Data", "Documento", "Vl. Tarifa", "Vl.Tx.Emb.", "Vl.Multa",
        "Vl.Rep. Terc.", "Tx.Adm", "Vl.Comissão", "Vl.Incentivo",
        "Vl.Desc", "Vl.Item Fatura", "OBS", "Bilhete"
    ]

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
    
    # Se arquivo_pdf for booleano ou inválido (ex: problema na conversão JS), evita erro
    if not arquivo_pdf:
        return pd.DataFrame(columns=colunas_padrao)

    reader = PdfReader(arquivo_pdf)
    total_pages = len(reader.pages)
    print(f"DEBUG: Iniciando processamento de {total_pages} páginas (Latam)...")

    for page_num, page in enumerate(reader.pages):
        # Tenta modo layout para manter colunas na mesma linha
        try:
            text = page.extract_text(extraction_mode="layout")
        except:
            text = page.extract_text()

        if not text:
            continue
            
        lines = text.split('\n')
        
        # DEBUG: Mostra o texto da primeira página para entender o formato com layout
        if page_num == 0:
            print(f"DEBUG: Amostra texto página 1 (Latam - Modo Layout):")
            print(text[:1000])
            print("-" * 40)
            print("DEBUG: Primeiras 10 linhas:")
            for i, L in enumerate(lines[:10]):
                print(f"[{i}] {L}")
            print("-" * 40)

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # DEBUG: Se encontrar algo parecido com uma data, imprime a linha
            if re.search(r"\d{2}/\d{2}/\d{4}", line):
                print(f"DEBUG: Linha com data encontrada: '{line}'")
                
            # Filtro de linhas inválidas
            if any(padrao.upper() in line.upper() for padrao in linhas_invalidas):
                continue

            # Captura de OBS (Tipo Item)
            # Ex: "Tipo Item: A VISTA"
            if "Tipo Item:" in line:
                match_obs = re.search(r"Tipo Item:\s*(.+)", line, re.IGNORECASE)
                if match_obs:
                    obs_atual = match_obs.group(1).strip()
                continue

            # Captura de Linha de Dados
            # Padrão esperado: DD/MM/YYYY + espaço + Documento + espaço + Valores...
            # Regex busca data no início da linha
            match_data = re.match(r"^(\d{2}/\d{2}/\d{4})\s+(.+)", line)
            
            if match_data:
                data = match_data.group(1)
                resto = match_data.group(2)
                
                # Tenta extrair o Documento
                # Documentos Latam geralmente têm hífens (957-...) ou são apenas números
                # O regex abaixo pega a primeira "palavra" que parece um documento
                match_doc = re.match(r"^([^\s]+)\s+(.+)", resto)
                
                if match_doc:
                    documento = match_doc.group(1)
                    valores_str = match_doc.group(2)
                    
                    # Extração de valores numéricos
                    # A lógica aqui deve ser robusta para diferentes formatos numéricos
                    # Procura por sequências que parecem números (com ponto ou vírgula)
                    # Ex: 100.00, 1,234.56, -50.00
                    # Note que o formatar_valor original espera formato americano (ponto para decimal) após limpar vírgulas
                    
                    # Regex para encontrar números float (positivos/negativos) na string
                    # Assume separação por espaços
                    partes = valores_str.split()
                    
                    # Filtra apenas o que parece número
                    valores_encontrados = []
                    for p in partes:
                        # Remove caracteres de moeda se houver (ex: R$, BRL)
                        p_limpo = p.replace('R$', '').replace('BRL', '')
                        # Verifica se parece número
                        if re.match(r'^-?[\d,.]+$', p_limpo):
                             valores_encontrados.append(p_limpo)

                    # Cria o registro
                    linha_padronizada = {col: "" for col in colunas_padrao}
                    linha_padronizada["Data"] = data
                    linha_padronizada["Documento"] = documento
                    linha_padronizada["OBS"] = obs_atual
                    linha_padronizada["Bilhete"] = gerar_bilhete(documento)

                    # Preenche colunas numéricas sequencialmente
                    # O original confia na ordem das colunas da tabela
                    # Aqui confiamos na ordem dos números encontrados na linha de texto
                    for i, col in enumerate(colunas_numericas):
                        if i < len(valores_encontrados):
                            linha_padronizada[col] = formatar_valor(valores_encontrados[i])
                        else:
                            linha_padronizada[col] = "0"
                            
                    dados.append(linha_padronizada)
                else:
                    # Se não conseguiu separar documento, log para debug (opcional)
                    # print(f"DEBUG: Falha ao extrair documento da linha: {line}")
                    pass

    # Cria DataFrame final
    df = pd.DataFrame(dados, columns=colunas_padrao)
    
    # Garante formatação zerada para colunas vazias
    for col in colunas_numericas:
        if col in df.columns:
            df[col] = df[col].replace("", "0")
            
    print(f"DEBUG: Total de registros extraídos: {len(df)}")
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
