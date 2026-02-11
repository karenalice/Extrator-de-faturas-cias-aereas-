# ✈️ Extrator de Faturas Aéreas (Azul, Gol, Latam)

> **Desenvolvido para a Confiança Turismo.** 💙

Bem-vindo ao **Extrator de Faturas Aéreas**, uma aplicação web moderna e eficiente para processamento automatizado de faturas de companhias aéreas. Este projeto utiliza **Python no navegador (via Pyodide)** para garantir privacidade total dos dados e alta performance.


## ✨ Funcionalidades

O sistema suporta a extração de dados das três principais companhias aéreas brasileiras:

| Companhia | Formato Suportado | Principais Dados Extraídos |
| :--- | :--- | :--- |
| **azul (AD)** | 📄 PDF (Nativo) | Bilhete, Data, Taxas (Emb/DU), Valores, OC/OD, Multas |
| **Gol (G3)** | 📝 TXT | PNR, Bilhete, Tarifa, Taxas, Valores Totais |
| **Latam (JJ)** | 📄 PDF (Nativo) | Documento, Valores Detalhados, Bilhete, Incentivos |

### 🚀 Destaques Técnicos
- **Processamento Local**: Seus arquivos **nunca** saem do seu computador. Tudo é processado pelo navegador.
- **Interface Premium**: Design moderno com *glassmorphism*, animações fluidas e tipografia limpa.
- **Exportação Excel**: Gera planilhas `.xlsx` formatadas e prontas para conferência.
- **Multiprocessamento**: Suporta múltiplos arquivos simultaneamente (especialmente para Gol/TXT).

---

## 🛠️ Tecnologias Utilizadas

- **Frontend**: HTML5, CSS3 (Variáveis CSS, Flexbox/Grid), JavaScript (ES6+ Modules).
- **Core de Processamento**: [Pyodide](https://pyodide.org/) (Python compilado para WebAssembly).
- **Bibliotecas Python**:
    - `pandas`: Manipulação e estruturação dos dados.
    - `pypdf`: Leitura e extração de texto de PDFs (Azul/Latam).
    - `openpyxl`: Geração de arquivos Excel.

---

## 📂 Estrutura do Projeto

```
/
├── index.html          # Dashboard principal
├── AD.html             # Página de extração Azul
├── G3.html             # Página de extração Gol
├── JJ.html             # Página de extração Latam
│
├── azul.py             # Lógica de extração (Python) - Azul
├── gol.py              # Lógica de extração (Python) - Gol
├── latam.py            # Lógica de extração (Python) - Latam
│
├── static/
│   ├── css/
│   │   └── style.css   # Estilos globais (Tema Premium)
│   ├── js/
│   │   ├── shared.js   # Gerenciador do Pyodide e dependências
│   │   ├── AD.js       # Interface específica Azul
│   │   ├── G3.js       # Interface específica Gol
│   │   └── JJ.js       # Interface específica Latam
│   └── img/            # Logotipos e assets
│
└── README.md           # Este arquivo
```

---

## ▶️ Como Usar

1.  **Abra o arquivo `index.html`** no seu navegador (Chrome, Edge ou Firefox recomendados).
2.  Selecione a companhia aérea desejada no painel principal.
3.  **Carregue seus arquivos**:
    - Para **Azul/Latam**: Arraste os PDFs da fatura.
    - Para **Gol**: Arraste os arquivos `.txt`.
4.  Aguarde o processamento (a primeira vez pode levar alguns segundos para carregar o Python).
5.  Confira a prévia dos dados na tabela.
6.  Clique em **"Exportar Excel"** para baixar o relatório final.

---

## ⚠️ Notas Importantes

- **Conexão**: Na primeira execução, é necessária internet para baixar o motor Pyodide. Nas próximas, o cache do navegador acelera o carregamento.
- **Privacidade**: Como o Python roda no seu navegador, dados sensíveis de passageiros e valores **não são enviados para nenhum servidor externo**.

---

Desenvolvido para otimizar a conferência de faturas aéreas. ✈️📊
