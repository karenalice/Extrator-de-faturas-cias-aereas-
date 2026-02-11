# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path

from pypdf import PdfReader
import pandas as pd

DEFAULT_DOWNLOADS = Path.home() / "Downloads"

# =========================
# REGEX
# =========================
RE_LOC_LINE = re.compile(r"^\s*([A-Z0-9]{6})\s*$")     # localizador SOMENTE se estiver sozinho na linha
RE_TKT = re.compile(r"\b(\d{10})\b")
RE_DATE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")

RE_NUM = re.compile(
    r"(?<!\w)(-?\d{1,3}(?:\.\d{3})*(?:,\d{2})|-?\d+(?:\.\d{2})|-?\d+(?:,\d{2}))(?!\w)"
)

RE_AGENCIA = re.compile(r"^\s*NOME\s+AGENCIA\s*:\s*(\d+)\s*[-–—]\s*(.+?)\s*$", re.IGNORECASE)
RE_TIPO = re.compile(r"^\s*([A-ZÇÃÕÉÊÍÓÚÁÜ\s]+)\s*:\s*$", re.IGNORECASE)

# códigos OC/OD
RE_OCOD_LINE = re.compile(r"^\s*(OC-[A-Z0-9]+|OD-CHG\d*|OD-[A-Z0-9]+)\s*$", re.IGNORECASE)
RE_OCOD_ANYWHERE = re.compile(r"\b(OC-|OD-CHG|OD-)\b", re.IGNORECASE)

# subtotal / totalizador
RE_SUBTOTAL_ANY = re.compile(r"\bSUBTOTAL\b", re.IGNORECASE)

NUM_FIELDS = [
    "TARIFA_A_VISTA", "TARIFA_CREDITO",
    "TAXAS_A_VISTA", "TAXAS_CREDITO",
    "DU_A_VISTA", "DU_CREDITO",
    "CC_DU", "COMISSAO", "INCENTIVO", "VALOR_LIQUIDO"
]

FINAL_COLS = [
    "LOCALIZADOR", "TIPO", "AGENCIA_COD", "AGENCIA_NOME",
    "NOME", "N_TKT", "DATA",
    "TARIFA_A_VISTA", "TARIFA_CREDITO",
    "TAXAS_A_VISTA", "TAXAS_CREDITO",
    "DU_A_VISTA", "DU_CREDITO",
    "CC_DU", "COMISSAO", "INCENTIVO", "VALOR_LIQUIDO",
    "OBSERVACOES",
    "PAGINA",
]


def to_float_any(s: str) -> float:
    if s is None:
        return 0.0
    s = str(s).strip()
    if s == "":
        return 0.0

    s = s.replace("−", "-").replace("–", "-")

    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")

    try:
        return float(s)
    except:
        return 0.0


def is_noise_line(line: str) -> bool:
    l = line.strip().upper()
    if not l:
        return True

    if "SUBTOTAL" in l:
        return True

    noise_starts = (
        "AZUL LINHAS AEREAS", "FATURA", "PERIODO", "VENCIMENTO",
        "MOEDA", "RLOC", "TARIFA", "TAXAS", "DU", "CC DU",
        "COMISSAO", "INCENTIVO", "VALOR", "VALOR LIQUIDO",
        "OBSERVACOES", "AGENTE MASTER", "CNPJ", "CEP", "ENDERECO",
        "PAGE", "PAG"
    )
    if l.startswith(noise_starts):
        return True

    if set(l) <= {"-", "_", "=", "|"}:
        return True

    return False


def _parse_vals_and_obs(s: str):
    """
    Extrai números e o texto após o último número (obs).
    Observações válidas = somente na linha principal (coluna Observações).
    """
    s = (s or "").replace("−", "-").replace("–", "-")
    matches = list(RE_NUM.finditer(s))
    nums = [m.group(1) for m in matches]
    vals = [to_float_any(n) for n in nums]

    obs = ""
    if matches:
        obs = s[matches[-1].end():].strip()
        obs = re.sub(r"\s{2,}", " ", obs).strip()

    return vals, obs


def _new_empty_record(meta: dict, page: int):
    rec = {
        "LOCALIZADOR": meta.get("LOCALIZADOR", ""),
        "TIPO": meta.get("TIPO", ""),
        "AGENCIA_COD": meta.get("AGENCIA_COD", ""),
        "AGENCIA_NOME": meta.get("AGENCIA_NOME", ""),
        "NOME": meta.get("NOME", ""),
        "N_TKT": meta.get("N_TKT", ""),
        "DATA": meta.get("DATA", ""),
        "OBSERVACOES": meta.get("OBSERVACOES", ""),
        "PAGINA": page,
    }
    for f in NUM_FIELDS:
        rec[f] = 0.0
    return rec


def _apply_vals_fill_or_sum_by_position(rec: dict, vals: list[float]):
    """
    Distribui por posição na ordem do relatório (linha principal e fallback).
    """
    for i, field in enumerate(NUM_FIELDS):
        if i >= len(vals):
            break
        v = float(vals[i])
        if abs(v) < 1e-12:
            continue
        cur = float(rec.get(field, 0.0) or 0.0)
        rec[field] = (cur + v) if abs(cur) > 1e-12 else v


def _taxas_from_vals(vals: list[float]):
    """
    Retorna (taxas_avista, taxas_credito) usando os 2 primeiros valores.
    """
    ta = float(vals[0]) if len(vals) >= 1 else 0.0
    tc = float(vals[1]) if len(vals) >= 2 else 0.0
    return ta, tc


def _is_all_zero_taxas(vals: list[float]) -> bool:
    ta, tc = _taxas_from_vals(vals)
    return abs(ta) < 1e-12 and abs(tc) < 1e-12


def _normalize_minus_zero(df: pd.DataFrame):
    for c in NUM_FIELDS:
        if c in df.columns:
            df[c] = df[c].apply(
                lambda x: 0.0 if (pd.notna(x) and abs(float(x)) < 1e-9) else (float(x) if pd.notna(x) else 0.0)
            )
    return df


def extract_records_from_pdf(pdf_source) -> pd.DataFrame:
    """
    pdf_source can be a Path or a file-like object (io.BytesIO).
    """
    records = []

    current_tipo = ""
    current_loc = ""
    agencia_cod = ""
    agencia_nome = ""

    last_record = None     # Último registro com tkt/data (ou OC/OD consolidado)
    pending_oc_code = None # Ex: "OC-NS" / "OC-DP"
    pending_name = ""      # Captura nome que pode estar na linha acima

    reader = PdfReader(pdf_source)
    total_pages = len(reader.pages)

    print(f"Total de páginas: {total_pages}")

    for pageno, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if not text:
            continue

        # NÃO resetamos last_record aqui → para permitir continuação entre páginas.

        for raw in text.splitlines():
            line = raw.rstrip().replace("−", "-").replace("–", "-")
            up = line.strip().upper()

            # ✅ SUBTOTAL: corta qualquer vínculo de continuação (novo bloco)
            if "SUBTOTAL" in up:
                last_record = None
                pending_oc_code = None
                pending_name = ""
                continue

            # Se for ruído (cabeçalhos repetitivos), ignoramos a linha,
            # mas mantemos last_record/pending_oc_code (pode ser fim de uma pág e início de outra).
            if is_noise_line(line):
                # Só resetamos o nome pendente se for uma mudança CLARA de contexto
                if any(x in up for x in ["NOME AGENCIA", "PERIODO", "AGENTE MASTER"]):
                    pending_name = ""
                continue

            # =========================
            # AJUSTE PRINCIPAL (páginas quebradas)
            # =========================

            # Agência
            m_ag = RE_AGENCIA.match(line)
            if m_ag:
                new_ag_cod = m_ag.group(1).strip()
                new_ag_nome = m_ag.group(2).strip()

                # Só reseta se realmente MUDOU a agência (não é cabeçalho repetido de nova página)
                changed = (agencia_cod and agencia_nome) and (
                    new_ag_cod != agencia_cod or new_ag_nome != agencia_nome
                )

                agencia_cod = new_ag_cod
                agencia_nome = new_ag_nome

                if changed:
                    last_record = None
                    pending_oc_code = None
                    pending_name = ""
                continue

            # Tipo (Vendas/Reembolso)
            m_tipo = RE_TIPO.match(line)
            if m_tipo:
                new_tipo = re.sub(r"\s{2,}", " ", m_tipo.group(1).strip()).replace(":", "").title()

                # Só reseta se realmente MUDOU o tipo (não é repetição no topo da próxima página)
                changed = (current_tipo != "" and new_tipo != current_tipo)

                current_tipo = new_tipo

                if changed:
                    last_record = None
                    pending_oc_code = None
                    pending_name = ""
                continue

            # Localizador (linha isolada de 6 chars)
            m_loc = RE_LOC_LINE.match(up)
            if m_loc:
                new_loc = m_loc.group(1).upper()

                # Só reseta se mudou o localizador
                changed = (current_loc != "" and new_loc != current_loc)

                current_loc = new_loc

                if changed:
                    last_record = None
                    pending_oc_code = None
                    pending_name = ""
                continue

            # ✅ OC-NS / OC-DP etc isolados
            m_oc = RE_OCOD_LINE.match(line.strip())
            if m_oc:
                pending_oc_code = m_oc.group(1).upper()

                # Se essa linha OC já tiver números, tentamos processar
                vals, _ = _parse_vals_and_obs(line)
                if vals and not _is_all_zero_taxas(vals):
                    # Se tiver last_record, vincula a ele
                    if last_record:
                        ta, tc = _taxas_from_vals(vals)
                        meta2 = {
                            "LOCALIZADOR": last_record["LOCALIZADOR"],
                            "TIPO": last_record["TIPO"],
                            "AGENCIA_COD": last_record["AGENCIA_COD"],
                            "AGENCIA_NOME": last_record["AGENCIA_NOME"],
                            "NOME": last_record["NOME"],
                            "N_TKT": pending_oc_code,
                            "DATA": last_record["DATA"],
                            "OBSERVACOES": last_record["OBSERVACOES"],
                            "PAGINA": pageno
                        }
                        rec2 = _new_empty_record(meta2, pageno)
                        rec2["TAXAS_A_VISTA"] = ta
                        rec2["TAXAS_CREDITO"] = tc
                        records.append(rec2)
                        pending_oc_code = None
                continue

            # TKT + DATA (Linha principal)
            m_tkt = RE_TKT.search(line)
            m_date = RE_DATE.search(line)

            if m_tkt and m_date:
                tkt = m_tkt.group(1)
                dt_txt = m_date.group(1)

                # Nome na própria linha
                nome_inline = line[:m_tkt.start()].strip()
                # Se o nome estiver na linha de cima (ou se for só "OC-DP")
                nome_final = nome_inline if len(nome_inline) > 3 else pending_name

                if not nome_final:
                    nome_final = "PASSAGEIRO DESCONHECIDO"

                after_date = line[m_date.end():]
                vals, obs = _parse_vals_and_obs(after_date)

                meta = {
                    "LOCALIZADOR": current_loc,
                    "TIPO": current_tipo,
                    "AGENCIA_COD": agencia_cod,
                    "AGENCIA_NOME": agencia_nome,
                    "NOME": nome_final,
                    "N_TKT": tkt,
                    "DATA": dt_txt,
                    "OBSERVACOES": obs,
                }

                rec = _new_empty_record(meta, pageno)
                _apply_vals_fill_or_sum_by_position(rec, vals)

                records.append(rec)
                last_record = rec
                pending_name = ""
                pending_oc_code = None
                continue

            # Se chegamos aqui, a linha NÃO tem TKT/DATA.
            # Pode ser:
            # 1. Nome do passageiro (preparando para a próxima linha)
            # 2. Valores de continuação do último passageiro
            # 3. Bloco OC/OD solto com valores

            vals, _ = _parse_vals_and_obs(line)

            if vals:
                # Se temos OC/OD pendente (seja da linha de cima ou desta)
                if pending_oc_code or RE_OCOD_ANYWHERE.search(line):
                    m_inline = re.search(r"\b(OC-[A-Z0-9]+|OD-CHG\d*|OD-[A-Z0-9]+)\b", line, re.IGNORECASE)
                    code = m_inline.group(1).upper() if m_inline else (pending_oc_code or "OC/OD")

                    if not _is_all_zero_taxas(vals):
                        # Vincula ao último passageiro se existir, senão usa contexto
                        ref = last_record if last_record else {"NOME": (pending_name or "AVULSO")}

                        ta, tc = _taxas_from_vals(vals)
                        meta2 = {
                            "LOCALIZADOR": current_loc,
                            "TIPO": current_tipo,
                            "AGENCIA_COD": agencia_cod,
                            "AGENCIA_NOME": agencia_nome,
                            "NOME": ref.get("NOME", "AVULSO"),
                            "N_TKT": code,
                            "DATA": ref.get("DATA", ""),
                            "OBSERVACOES": ref.get("OBSERVACOES", ""),
                        }
                        rec2 = _new_empty_record(meta2, pageno)
                        rec2["TAXAS_A_VISTA"] = ta
                        rec2["TAXAS_CREDITO"] = tc
                        records.append(rec2)

                    pending_oc_code = None

                elif last_record:
                    # É uma continuação numérica normal do último passageiro
                    _apply_vals_fill_or_sum_by_position(last_record, vals)

            else:
                # Não tem números. Se não for ruído e tiver algum texto, pode ser o nome
                clean = line.strip()
                if len(clean) > 3 and not any(x in up for x in ["MOEDA", "RLOC", "TKT", "DATE"]):
                    pending_name = clean

        if pageno % 10 == 0 or pageno == total_pages:
            print(f"Processando: {pageno}/{total_pages} páginas...")

    print(f"DEBUG: Total de registros extraídos (Azul): {len(records)}")

    df = pd.DataFrame(records)
    if df.empty:
        return df

    # Limpeza final e normalização
    df["DATA"] = pd.to_datetime(df["DATA"], format="%d/%m/%Y", errors="coerce").dt.date
    df = _normalize_minus_zero(df)

    for c in FINAL_COLS:
        if c not in df.columns:
            df[c] = "" if c not in NUM_FIELDS else 0.0

    return df[FINAL_COLS].reset_index(drop=True)


if __name__ == "__main__":
    # Local CLI testing (only if run directly with python)
    try:
        if len(sys.argv) >= 2:
            pdf_path = Path(sys.argv[1])
            df = extract_records_from_pdf(pdf_path)
            out_path = pdf_path.with_suffix(".xlsx")
            df.to_excel(out_path, index=False)
            print(f"Exported: {out_path}")
    except:
        pass
