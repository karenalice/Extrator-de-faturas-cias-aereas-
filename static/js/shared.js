// Compatilhado entre todas as páginas
let pyodide;
let currentDF;
let _pyodideInitPromise = null;

// Função principal de inicialização do Pyodide
async function initPyodide() {
    const loadingOverlay = document.getElementById("loading-overlay");
    const loadingText = document.getElementById("loading-text");

    if (!loadingOverlay) return;

    if (_pyodideInitPromise) return _pyodideInitPromise;

    _pyodideInitPromise = (async () => {
        loadingOverlay.style.display = "flex";
        loadingText.textContent = "Carregando Python (Pyodide)...";

        try {
            pyodide = await loadPyodide();
            const airline = document.body.dataset.airline;

            loadingText.textContent = "Carregando pacotes...";
            await ensurePythonPackages(airline, loadingText);

            loadingText.textContent = "Carregando lógica de extração...";
            await loadAirlineScript(airline);

            loadingText.textContent = "Pronto!";

            const processBtn = document.getElementById("btn-processar");
            if (processBtn) {
                processBtn.disabled = false;
                processBtn.textContent = airline === "G3" ? "Processar Arquivos" : "Processar PDF";
            }

        } catch (error) {
            console.error("Pyodide Init Error:", error);
            loadingText.innerHTML =
                `<strong>Erro ao inicializar:</strong><br>${error.message}<br><br>` +
                `Recarregue a página. Se persistir, abra o Console (F12) e envie o erro.`;
            _pyodideInitPromise = null; // permite tentar novamente
            throw error;
        } finally {
            if (pyodide && pyodide.runPython) {
                setTimeout(() => {
                    loadingOverlay.style.display = "none";
                }, 400);
            }
        }
    })();

    return _pyodideInitPromise;
}

// Instalação de pacotes com tratamento de conflitos
async function ensurePythonPackages(airline, loadingText) {
    await pyodide.loadPackage("pandas");
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");

    const hasModule = (modName) => {
        return pyodide.runPython(`
import importlib.util
importlib.util.find_spec("${modName}") is not None
    `);
    };

    if (!hasModule("openpyxl")) {
        await micropip.install("openpyxl");
    }

    if (airline === "AD" || airline === "JJ") {
        if (!hasModule("pypdf")) {
            loadingText.textContent = "Instalando leitor de PDF (pypdf)...";
            try {
                // pypdf é uma biblioteca pura Python, compatível com Pyodide
                await micropip.install("pypdf");
            } catch (e) {
                console.error("Erro ao instalar pypdf:", e);
                throw new Error("Não foi possível instalar o leitor de PDF. Detalhes: " + e.message);
            }
        }
    }
}

// Carrega o script Python específico
async function loadAirlineScript(airline) {
    let scriptName = null;
    if (airline === "G3") scriptName = "gol.py";
    if (airline === "AD") scriptName = "azul.py";
    if (airline === "JJ") scriptName = "latam.py";

    if (scriptName) {
        const response = await fetch(scriptName);
        if (!response.ok) throw new Error(`Falha ao carregar ${scriptName}`);
        const content = await response.text();
        pyodide.runPython(content);
    }
}

// Renderiza tabela HTML
function renderTable(columns, data) {
    const tableContainer = document.getElementById("data-table-container");
    if (!tableContainer) return;

    let html = "<table><thead><tr>";
    columns.forEach((col) => (html += `<th>${col}</th>`));
    html += "</tr></thead><tbody>";

    data.forEach((row) => {
        html += "<tr>";
        columns.forEach((col) => {
            html += `<td>${row[col] === null ? "" : row[col]}</td>`;
        });
        html += "</tr>";
    });

    html += "</tbody></table>";
    tableContainer.innerHTML = html;
}

// Exporta para Excel
async function exportToExcel(airline) {
    if (!currentDF) return;

    try {
        const excelBytesProxy = pyodide.runPython(
            `
import io
output = io.BytesIO()
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    current_df_global.to_excel(writer, index=False)
output.getvalue()
          `,
            { globals: pyodide.globals.copy().set("current_df_global", currentDF) }
        );

        const excelBytes = excelBytesProxy.toJs();
        excelBytesProxy.destroy();

        const blob = new Blob([excelBytes], {
            type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `extracao_${airline}_${new Date().getTime()}.xlsx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    } catch (error) {
        console.error("Export Error:", error);
        alert("Erro ao gerar Excel: " + error.message);
    }
}

// Inicialização automática ao carregar a página
document.addEventListener("DOMContentLoaded", () => {
    const airline = document.body.dataset.airline;
    if (airline) {
        initPyodide();
    }

    // Setup do input de arquivo (visual)
    const fileInput = document.getElementById("file-upload");
    if (fileInput) {
        fileInput.addEventListener("change", (e) => {
            const fileName = e.target.files.length > 1
                ? `${e.target.files.length} arquivos selecionados`
                : e.target.files[0].name;
            document.getElementById("file-name-display").textContent = fileName;
        });
    }

    // Setup do botão de exportar (comum a todos)
    const exportBtn = document.getElementById("btn-exportar");
    if (exportBtn) {
        exportBtn.addEventListener("click", () => exportToExcel(airline));
    }
});
