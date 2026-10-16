# Estudio de edición — auditoría de cortes de una fuente: revisa TODAS las fronteras entre frases y marca dónde un corte caería sobre voz.
#   python audit_cuts.py   -> lista de fronteras "pegadas" (frases dichas sin pausa) que el selector debe evitar como borde de escena
import sys
import plan as P, content as C
from core import FPS


def audit(thr=-28.0):
    rows = []
    for k in range(len(C.SENT) - 1):
        a, b = C.SENT[k], C.SENT[k + 1]
        fo, fi = P.cut_out(a["e"]), P.cut_in(b["s"])
        voz_cruzada = fo > fi + 1 and (P.R[fi:fo] > -36).any()          # la salida de una frase incluye voz de la siguiente
        pegada = max(P.edge_db(fo), P.edge_db(fi)) > thr                  # no hay hueco audible entre las dos frases
        rows.append(dict(k=k, out=fo / FPS, inn=fi / FPS, db=round(max(P.edge_db(fo), P.edge_db(fi)), 1), cruzada=bool(voz_cruzada), pegada=bool(pegada),
                         a=a["text"][-28:], b=b["text"][:28], spk=a["spk"] + b["spk"]))
    return rows


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    rows = audit()
    bad = [r for r in rows if r["cruzada"]]
    glued = [r for r in rows if r["pegada"]]
    print(f"fronteras: {len(rows)} · voz cruzada: {len(bad)} · pegadas (sin hueco): {len(glued)}")
    for r in bad: print("  CRUZADA", r)
    for r in glued: print(f"  pegada {r['spk']} {r['db']:6.1f} dB  …{r['a']} | {r['b']}…")
