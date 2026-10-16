# Estilo REDES (la casa, 2026): el look que el equipo de Lilian publica de verdad en TikTok, medido sobre 18 videos editados
# (analysis/tiktok2610, STUDIO_LOG §3o). Video a pantalla completa con la cara arriba del centro (y≈0.32), color natural sin
# viñeta ni grano, subtítulo ÚNICO blanco con contorno negro de 2-4 palabras centrado a 0.641 del alto, gancho en BLANCO Y NEGRO
# limpio (la frase fuerte de más adelante, 3-4 s) que entra al color con un barrido desenfocado, música baja (≈18 dB bajo la
# voz) que sigue en la tarjeta final blanca de 3 s con las redes. Sin placa de nombre, sin palabras en color, sin efectos.
from styles.base import *

CAP_PX = 54


class Style(Base):
    anchor = (540.0, 614.0)              # cara a 0.32 del alto (mediana de las referencias)
    cap_x, cap_y = 540, 1231             # 0.641 × 1920 (14 de 18 referencias)
    grain = 0.0
    show_name = False

    def init(self):
        c = self.c
        # el gancho puede ser pregunta + respuesta (hook_8 H + hook_9 A): el blanco y negro cubre TODO el gancho y el color entra
        # cuando empieza el contenido (si no, el color cortaba la pregunta por la mitad)
        hk = [v["o1"] for v in c.SC.values() if str(v.get("sid", "")).startswith("hook")]
        self.bw_end = max(hk + [c.hook_end]) if hk else 0.0            # sin gancho (declaración completa): nada en blanco y negro
        self.hook_end_t = self.bw_end
        if c.cfg.get("gancho") == "color": self.bw_end = 0.0           # gancho en color (referencias N03/N04/N07/N21/N34): solo el barrido
        self.whips_f = [int(round(self.hook_end_t * FPS))] if self.hook_end_t > 0.5 else []
        from styles.cifras_capa import Cifras
        self.cif = Cifras(self)                  # cifras en pantalla: solo si ella dice estadísticas de peso (cfg "cifras")
        from styles.insertos_capa import Insertos
        self.ins = Insertos(self, avoid=[(s_["t0"], s_["t1"]) for s_ in self.cif.items])   # noticias / documentos / infografías (cfg "insertos")
        from styles.broll_capa import Broll
        self.broll = Broll(self, avoid=[(s_["t0"], s_["t1"]) for s_ in self.cif.items] + self.ins.spans())   # público sobre la voz (cfg "broll")

    def zoom(self, n, it, t):
        return 1.0                       # el zoom lo fija core.ZOOM_FIJO (acercamiento fijo a la cara)

    def look(self, x, n, t):
        if t < self.bw_end:              # gancho: blanco y negro limpio (sin polvo ni sacudida, como en las referencias)
            g = 0.299 * x[0:1] + 0.587 * x[1:2] + 0.114 * x[2:3]
            return ((g - 0.5) * 1.12 + 0.5).clamp(0, 1).repeat(3, 1, 1)      # copia real: encima se dibujan los subtítulos
        return grade_color(x, contrast=1.03, sat=1.02)

    def cap_sprite(self, k):
        if self.scene_spk.get(k["sc"]) == "R": return self.rep_sprite(k)
        return sub_sprite(k["words"], key_color=None, px=CAP_PX)       # un solo estilo: blanco, contorno negro, sin claves en color

    def draw_captions(self, fr, t):
        ci, k = self.chunk_at(t)
        if k is None: return
        if ci not in self.chunk_cache: self.chunk_cache[ci] = spr_t(self.cap_sprite(k))
        spr = self.chunk_cache[ci]
        blend(fr, spr, self.cap_x - spr.shape[2] / 2, self.cap_y - spr.shape[1] / 2)    # aparece de golpe, sin animación (referencias)

    def decorate(self, x, n, it, t):
        if t >= self.hook_end_t: self.cif.draw(x, t)
        self.draw_captions(x, t)
        return x

    def compose(self, n, it, rd):
        c = self.c
        if it["kind"] == "card": return self.end.frame((n - c.END0) / FPS)
        x = self.look(self.video(n, it, rd), n, n / FPS)                # (se lee igual: el lector de la fuente sigue sincronizado)
        b = self.broll.frame(n / FPS)
        if b is not None: x = b                                            # toma del público tapando el salto; la voz sigue
        x = self.ins.draw(x, n / FPS)                                      # inserto de contexto a pantalla completa (la voz sigue)
        x = self.decorate(x, n, it, n / FPS)
        k, off = whip_k(n, self.whips_f)
        x = whip_filter(x, k, off)
        return exit_to_white(x, self.end0 - n)

    def whips(self): return self.whips_f

    def cues(self):
        c = self.c; out = []
        for f in self.whips_f: out.append((f / FPS - 0.14, "whoosh", 0.30))
        out += self.cif.cues()
        out.append((c.END0 / FPS + 0.28, "chime", 0.26))
        return out
