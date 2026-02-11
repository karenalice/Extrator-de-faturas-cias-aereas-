# 📘 Guia Técnico e de Desenvolvimento

Este documento detalha a arquitetura técnica, a lógica de extração e como o sistema funciona "por baixo do capô".

---

## 🏗️ Arquitetura: Pyodide e WebAssembly

Diferente de sistemas web tradicionais que enviam arquivos para um servidor (Backend), este projeto utiliza **Pyodide**.

### Como funciona o fluxo?
1.  **Carregamento (`shared.js`)**: Ao abrir a página, o navegador baixa o interpretador CPython compilado para WebAssembly (`pyodide.js`).
2.  **Instalação de Pacotes**: O `micropip` instala `pandas`, `pypdf` e `openpyxl` diretamente na memória do navegador.
3.  **Execução**:
    - O JavaScript lê o arquivo do usuário como um `ArrayBuffer`.
    - Esse buffer é convertido para um objeto Python.
    - O script Python específico (`azul.py`, etc.) processa os bytes e retorna um DataFrame do Pandas.
4.  **Retorno**: O DataFrame é convertido para JSON (para exibição na tabela HTML) ou para Excel (blob) para download.

---

## 🧠 Lógica de Extração (Python)

Cada arquivo `.py` na raiz contém uma função principal de entrada e várias funções auxiliares.

### 1. Azul (`azul.py`)
**Desafio**: PDFs complexos com quebras de página no meio de registros e dados (como nomes) fora de alinhamento.
- **Bibliotecas**: `pypdf` para extração de texto bruto.
- **Estratégia**:
    - Usa **Regex** (`re`) para identificar linhas de tickets (`RE_TKT`), datas e valores.
    - **Gestão de Estado**: Mantém variáveis como `last_record` e `pending_oc_code` para lidar com passageiros que começam em uma página e terminam em outra.
    - **Lógica de Continuação**: Se uma linha tem apenas números, o sistema assume que são taxas extras do último passageiro identificado.
    - **Tratamento de OC/OD**: Identifica códigos de "Outras Cobranças" (OC) e cria registros separados se necessário.

### 2. Gol (`gol.py`)
**Desafio**: Arquivos de texto posicional ou separação por ponto-e-vírgula variável.
- **Estratégia**:
    - Lê o arquivo como texto (`latin1` ou `utf-8`).
    - Identifica o cabeçalho `PNR;Bilhete;...`.
    - Itera linha a linha, capturando o `tipo_atual` (ex: "Vendas", "Reembolsos") que aparece como título de seção.
    - Valida se a linha tem o número mínimo de colunas antes de adicionar ao dataset.

### 3. Latam (`latam.py`)
**Desafio**: PDFs "Layout" onde a posição visual importa.
- **Estratégia**:
    - Tenta usar `extract_text(extraction_mode="layout")` do `pypdf` para preservar o alinhamento visual.
    - Busca padrões de (Data + Documento + Valores) usando Regex.
    - **Limpeza Numérica**: Remove símbolos de moeda (R$, BRL) e converte formatação brasileira (1.000,00) para float Python.

---

## 💻 Frontend (HTML/JS/CSS)

### Modularização
Para evitar um código monolítico, o JavaScript foi dividido:
- `shared.js`: Código comum (carregar Pyodide, renderizar tabela, exportar Excel).
- `AD.js`, `G3.js`, `JJ.js`: Listeners de eventos específicos de cada página e chamadas para as funções Python respectivas.

### Estilização (`style.css`)
- **Variáveis CSS**: Cores e espaçamentos definidos no `:root` para fácil manutenção.
- **Layout Responsivo**: Uso de `flexbox` e `grid` para adaptar de monitores wide a telas menores.
- **Glassmorphism**: Uso de `backdrop-filter: blur()` no cabeçalho para efeito visual moderno.

---

## 🔧 Manutenção e Extensão

### Como adicionar uma nova Cia Aérea?
1.  Crie `NOVA.html` com a estrutura base.
2.  Crie `nova.py` com a função `extract_nova_data(file_bytes)`.
3.  Crie `static/js/NOVA.js` chamando a função Python.
4.  Adicione a chamada em `shared.js` na função `loadAirlineScript`.
5.  Adicione o link no menu em `index.html`.

### Debugging
- Erros do Python aparecem no **Console do Navegador** (F12).
- Use `print()` no código Python; a saída será exibida no console JS.

---

**Autor**: Departamento de BI | **Versão**: 2.0 (Pyodide/Client-Side)
