import pandas as pd
import io

# Variável global
dados_extraidos = None

def linha_valida(campos):
    """
    Regras:
    - Tem que ter pelo menos 3 colunas
    - PNR, Bilhete e Data não podem estar vazios
    - Não pode ser só zeros ou vazio
    """
    if len(campos) < 3:
        return False
    if campos[0].strip() == "" or campos[1].strip() == "" or campos[2].strip() == "":
        return False
    if all(c.strip() in {"", "0", "0,00"} for c in campos):
        return False
    return True

def extract_gol_data(files_data):
    """
    files_data is a list of tuples: (filename, content_bytes)
    """
    todos_dados = []
    for nome_arquivo, content in files_data:
        try:
            # Se for memoryview (comum no Pyodide), converte para bytes
            if isinstance(content, memoryview):
                content = bytes(content)
                
            texto = content.decode('utf-8')
        except UnicodeDecodeError:
            texto = content.decode('latin1')
        except AttributeError:
             # Caso já seja string (não deveria acontecer, mas por segurança)
             texto = str(content)
        
        linhas = texto.splitlines()

        dados = []
        capturar = False
        cabecalho = []
        tipo_atual = ""

        for linha in linhas:
            linha = linha.strip()
            if linha.startswith("Total - A Vista / A Crédito"):
                break
            if not capturar and linha.startswith("PNR;Bilhete;Data;Tarifa à Vista;"):
                cabecalho = linha.split(";")
                capturar = True
                continue
            if capturar:
                if ";" in linha:
                    campos = linha.split(";")
                    if linha_valida(campos):
                        dados.append([nome_arquivo] + campos + [tipo_atual])
                elif linha.strip():
                    tipo_atual = linha.strip()
        if dados:
            colunas = ["FONTE"] + cabecalho + ["TIPO"]
            df_parcial = pd.DataFrame(dados, columns=colunas)
            todos_dados.append(df_parcial)
    
    if not todos_dados:
        return pd.DataFrame()
    
    return pd.concat(todos_dados, ignore_index=True)
