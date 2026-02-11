// Lógica específica para GOL (G3)
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
                alert("Por favor, selecione ao menos um arquivo TXT.");
                return;
            }

            loadingOverlay.style.display = "flex";
            document.getElementById("loading-text").textContent = "Processando arquivos GOL...";
            tableContainer.innerHTML = "";
            exportBtn.style.display = "none";

            try {
                await initPyodide(); // Garante que o ambiente está pronto

                const filesData = [];
                for (const file of files) {
                    const buffer = await file.arrayBuffer();
                    filesData.push([file.name, new Uint8Array(buffer)]);
                }

                pyodide.globals.set("temp_files_data", filesData);
                const df = pyodide.runPython(`extract_gol_data(temp_files_data.to_py())`);

                if (df && !df.empty) {
                    currentDF = df;

                    // Renderização otimizada
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
                        warn.innerText = `Mostrando somente 200 linhas na tela. O Excel terá todas as ${nRows} linhas.`;
                        tableContainer.appendChild(warn);
                    }

                    exportBtn.style.display = "inline-block";
                } else {
                    alert("Nenhum dado encontrado nos arquivos.");
                }
            } catch (error) {
                console.error("G3 Processing Error:", error);
                alert("Erro ao processar: " + error.message);
            } finally {
                loadingOverlay.style.display = "none";
            }
        });
    }
});
