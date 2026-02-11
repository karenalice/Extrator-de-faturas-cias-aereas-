// Lógica específica para AZUL (AD)
document.addEventListener("DOMContentLoaded", () => {
    const uploadBtn = document.getElementById("btn-processar");
    const fileInput = document.getElementById("file-upload");
    const exportBtn = document.getElementById("btn-exportar");
    const loadingOverlay = document.getElementById("loading-overlay");
    const tableContainer = document.getElementById("data-table-container");

    if (uploadBtn) {
        uploadBtn.addEventListener("click", async () => {
            const files = fileInput.files;
            if (files.length === 0) {
                alert("Por favor, selecione ao menos um arquivo PDF.");
                return;
            }

            loadingOverlay.style.display = "flex";
            document.getElementById("loading-text").textContent = "Processando PDF Azul...";
            tableContainer.innerHTML = "";
            exportBtn.style.display = "none";

            try {
                await initPyodide();

                const dfs = [];
                for (const file of files) {
                    const buffer = await file.arrayBuffer();
                    const bytes = new Uint8Array(buffer);

                    // Converte para Python bytes corretamente
                    const pythonBytes = pyodide.runPython(`
import io
def create_buffer(js_bytes):
    # Converte JsProxy para bytes Python
    py_bytes = bytes(js_bytes.to_py())
    return io.BytesIO(py_bytes)
create_buffer
                    `);

                    const pdfBuffer = pythonBytes(bytes);

                    // Chama a função específica do azul.py
                    pyodide.globals.set("pdf_buffer", pdfBuffer);
                    const current_df = pyodide.runPython("extract_records_from_pdf(pdf_buffer)");
                    dfs.push(current_df);
                }

                const df = pyodide.globals.set("temp_dfs", dfs);
                const finalDF = pyodide.runPython(
                    "pd.concat(temp_dfs, ignore_index=True) if len(temp_dfs) > 0 else pd.DataFrame()"
                );

                if (finalDF && !finalDF.empty) {
                    currentDF = finalDF;

                    const nRows = pyodide.runPython("len(current_df_global)", {
                        globals: pyodide.globals.copy().set("current_df_global", currentDF),
                    });

                    const toShow = nRows > 200
                        ? pyodide.runPython("current_df_global.head(200)", {
                            globals: pyodide.globals.copy().set("current_df_global", currentDF),
                        })
                        : currentDF;

                    const jsonStr = pyodide.runPython("df.to_json(orient='records')", {
                        globals: pyodide.globals.copy().set("df", toShow)
                    });
                    const data = JSON.parse(jsonStr);
                    const columns = pyodide.runPython("list(df.columns)", {
                        globals: pyodide.globals.copy().set("df", toShow)
                    });

                    renderTable(columns, data);

                    if (nRows > 200) {
                        const warn = document.createElement("div");
                        warn.style.marginTop = "12px";
                        warn.style.fontSize = "0.9rem";
                        warn.innerText = `Mostrando somente 200 linhas. O Excel terá todas as ${nRows} linhas.`;
                        tableContainer.appendChild(warn);
                    }

                    exportBtn.style.display = "inline-block";
                } else {
                    alert("Nenhum dado encontrado no PDF.");
                }

            } catch (error) {
                console.error("AD Processing Error:", error);
                alert("Erro ao processar PDF: " + error.message);
            } finally {
                loadingOverlay.style.display = "none";
            }
        });
    }
});
