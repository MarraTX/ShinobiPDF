"""Componentes de interfaz reutilizables."""
import os
import threading
import tkinter

import customtkinter as ctk
import fitz  # PyMuPDF
from PIL import Image, ImageTk

from . import theme
from .theme import C, font, icon, resolve
from .core import formatear_tamano
from .i18n import t


# ----------------------------------------------------
# Botones y contenedores
# ----------------------------------------------------
_VARIANTS = {
    "primary": dict(fg_color=C["accent"], hover_color=C["accent_hover"], text_color=C["on_accent"], icon_color="on_accent"),
    "success": dict(fg_color=C["success"], hover_color=C["success_hover"], text_color=C["on_accent"], icon_color="on_accent"),
    "secondary": dict(fg_color=C["surface_alt"], hover_color=C["hover"], text_color=C["text"], border_width=1, border_color=C["border"], icon_color="text"),
    "ghost": dict(fg_color="transparent", hover_color=C["hover"], text_color=C["text"], icon_color="muted"),
    "danger_ghost": dict(fg_color="transparent", hover_color=C["danger_soft"], text_color=C["danger"], icon_color="danger"),
}
_SIZES = {"sm": (28, 14, 12), "md": (34, 16, 13), "lg": (44, 18, 15)}


def button(master, text="", icon_name=None, variant="secondary", size="md", tooltip=None, **kwargs):
    estilo = dict(_VARIANTS[variant])
    color_icono = estilo.pop("icon_color")
    alto, tam_icono, tam_fuente = _SIZES[size]
    imagen = icon(icon_name, tam_icono, color_icono) if icon_name else None
    if not text and imagen is None and icon_name:
        text = "•"  # Sin fuente de íconos: al menos algo visible
    opciones = dict(text=text, image=imagen, compound="left", height=alto, corner_radius=8,
                    font=font(tam_fuente, "bold" if variant in ("primary", "success") else "normal"),
                    text_color_disabled=C["faint"])
    if not text:
        opciones["width"] = alto
    opciones.update(estilo)
    opciones.update(kwargs)
    btn = ctk.CTkButton(master, **opciones)
    btn._variant_fg = opciones["fg_color"]
    if tooltip:
        Tooltip(btn, tooltip)
    return btn


def set_enabled(btn, enabled):
    """Habilita/deshabilita un botón con un aspecto claramente distinto cuando está apagado."""
    fg = getattr(btn, "_variant_fg", None)
    disabled_fg = C["surface_alt"] if fg not in (None, "transparent") else "transparent"
    btn.configure(state="normal" if enabled else "disabled", fg_color=fg if enabled else disabled_fg)


def card(master, **kwargs):
    opciones = dict(fg_color=C["surface"], corner_radius=14, border_width=1, border_color=C["border"])
    opciones.update(kwargs)
    return ctk.CTkFrame(master, **opciones)


def label(master, text="", size=13, weight="normal", color="text", **kwargs):
    return ctk.CTkLabel(master, text=text, font=font(size, weight), text_color=C.get(color, color), **kwargs)


def entry(master, placeholder="", width=120, **kwargs):
    opciones = dict(placeholder_text=placeholder, width=width, height=32, corner_radius=8, font=font(13),
                    fg_color=C["input"], border_color=C["border"], border_width=1, text_color=C["text"],
                    placeholder_text_color=C["faint"])
    opciones.update(kwargs)
    return ctk.CTkEntry(master, **opciones)


def checkbox(master, text, variable, tooltip=None, **kwargs):
    cb = ctk.CTkCheckBox(master, text=text, variable=variable, font=font(12), text_color=C["text"],
                         checkbox_width=18, checkbox_height=18, corner_radius=5, border_width=2,
                         fg_color=C["accent"], hover_color=C["accent_hover"], border_color=C["faint"], **kwargs)
    if tooltip:
        Tooltip(cb, tooltip)
    return cb


def segmented(master, values, command=None, **kwargs):
    return ctk.CTkSegmentedButton(master, values=values, command=command, height=32, font=font(12, "bold"),
                                  corner_radius=8, fg_color=C["surface_alt"], selected_color=C["accent"],
                                  selected_hover_color=C["accent_hover"], unselected_color=C["surface_alt"],
                                  unselected_hover_color=C["hover"], text_color=(C["text"][0], C["text"][1]),
                                  **kwargs)


# ----------------------------------------------------
# Ventanas secundarias
# ----------------------------------------------------
def window_scaling(widget):
    return ctk.ScalingTracker.get_window_scaling(widget)


def center_on_parent(parent, win):
    """Centra una ventana secundaria sobre la principal, ajustada a su contenido."""
    win.update_idletasks()
    scaling = window_scaling(parent)
    req_w, req_h = win.winfo_reqwidth(), win.winfo_reqheight()
    x = parent.winfo_rootx() + (parent.winfo_width() - req_w) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - req_h) // 2
    x = max(0, min(x, parent.winfo_screenwidth() - req_w))
    y = max(0, min(y, parent.winfo_screenheight() - req_h))
    win.geometry(f"{int(req_w / scaling)}x{int(req_h / scaling)}+{x}+{y}")


def make_modal(parent, win):
    win.transient(parent)
    win.lift()

    def grab():
        # grab_set falla si la ventana todavía no es visible
        try:
            if win.winfo_exists():
                win.grab_set()
                win.focus_force()
        except tkinter.TclError:
            win.after(50, grab)
    win.after(100, grab)


class Dialog(ctk.CTkToplevel):
    """Diálogo modal con ícono, título, mensaje, detalle opcional y botones."""
    KINDS = {"error": ("error", "danger"), "success": ("check", "success"), "info": ("info", "accent"),
             "warning": ("warning", "warning"), "question": ("info", "accent")}

    def __init__(self, parent, title, message, kind="info", buttons=None, detail=None):
        super().__init__(parent)
        buttons = buttons or ((t("ok"), True, "primary"),)
        self.result = None
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=C["surface"])

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=(22, 16))

        nombre_icono, color = self.KINDS.get(kind, self.KINDS["info"])
        # El círculo de fondo va dibujado en la imagen para que no se deforme
        icono = ctk.CTkLabel(body, text="", image=theme.icon_badge(nombre_icono, 46, 24, color, "surface_alt"))
        icono.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 16))
        label(body, title, 16, "bold", anchor="w", justify="left").grid(row=0, column=1, sticky="w")
        label(body, message, 13, color="muted", wraplength=360, anchor="w", justify="left").grid(row=1, column=1, sticky="w", pady=(4, 0))

        if detail:
            caja = ctk.CTkTextbox(body, width=360, height=110, font=font(12), fg_color=C["input"],
                                  border_color=C["border"], border_width=1, corner_radius=8, text_color=C["text"])
            caja.insert("1.0", detail)
            caja.configure(state="disabled")
            caja.grid(row=2, column=1, sticky="ew", pady=(10, 0))

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", padx=24, pady=(0, 20))
        principal = None
        for texto, valor, variante in reversed(buttons):
            btn = button(fila, texto, variant=variante, width=110, command=lambda v=valor: self.close(v))
            btn.pack(side="right", padx=(8, 0))
            if variante in ("primary", "success") and principal is None:
                principal = valor

        cancelar = buttons[-1][1] if len(buttons) > 1 else buttons[0][1]
        self.bind("<Return>", lambda e: self.close(principal if principal is not None else buttons[0][1]))
        self.bind("<Escape>", lambda e: self.close(cancelar))
        self.protocol("WM_DELETE_WINDOW", lambda: self.close(cancelar))

        center_on_parent(parent, self)
        make_modal(parent, self)

    def close(self, value):
        self.result = value
        try:
            self.grab_release()
        except tkinter.TclError:
            pass
        self.destroy()

    @classmethod
    def alert(cls, parent, title, message, kind="error", detail=None):
        cls(parent, title, message, kind, detail=detail)

    @classmethod
    def confirm(cls, parent, title, message, ok_text=None, danger=False):
        dlg = cls(parent, title, message, "warning" if danger else "question",
                  buttons=((ok_text or t("continue"), True, "primary"), (t("cancel"), False, "secondary")))
        parent.wait_window(dlg)
        return bool(dlg.result)


class PasswordDialog(ctk.CTkToplevel):
    """Pide la contraseña de un PDF protegido."""

    def __init__(self, parent, filename, error=None):
        super().__init__(parent)
        self.result = None
        self.title(t("pw_window_title"))
        self.resizable(False, False)
        self.configure(fg_color=C["surface"])

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=(22, 10))
        ctk.CTkLabel(body, text="", image=theme.icon_badge("lock", 46, 22, "accent", "surface_alt")).grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 16))
        label(body, t("pw_title"), 16, "bold", anchor="w").grid(row=0, column=1, sticky="w")
        label(body, t("pw_message", file=filename), 13, color="muted", wraplength=320,
              anchor="w", justify="left").grid(row=1, column=1, sticky="w", pady=(4, 0))
        self.entry = entry(body, t("pw_placeholder"), width=320, show="•")
        self.entry.grid(row=2, column=1, sticky="ew", pady=(12, 0))
        self.error = label(body, error or "", 12, color="danger", anchor="w")
        self.error.grid(row=3, column=1, sticky="w", pady=(4, 0))
        if not error:
            self.error.grid_remove()

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", padx=24, pady=(4, 20))
        button(fila, t("open"), variant="primary", width=110, command=self._ok).pack(side="right", padx=(8, 0))
        button(fila, t("cancel"), variant="secondary", width=110, command=self._cancel).pack(side="right")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        center_on_parent(parent, self)
        make_modal(parent, self)
        self.after(150, self.entry.focus_set)

    def _ok(self):
        self.result = self.entry.get()
        self._close()

    def _cancel(self):
        self.result = None
        self._close()

    def _close(self):
        try:
            self.grab_release()
        except tkinter.TclError:
            pass
        self.destroy()

    @classmethod
    def ask(cls, parent, filename, error=None):
        dlg = cls(parent, filename, error)
        parent.wait_window(dlg)
        return dlg.result


class ProgressDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, cancellable=True):
        super().__init__(parent)
        self.cancel_event = threading.Event()
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=C["surface"])
        self.protocol("WM_DELETE_WINDOW", self.request_cancel if cancellable else (lambda: None))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=26, pady=22)
        cabecera = ctk.CTkFrame(body, fg_color="transparent")
        cabecera.pack(fill="x")
        self._frames = theme.shuriken_frames(30)
        self._frame = 0
        self.spinner = ctk.CTkLabel(cabecera, text="", image=self._frames[0] if self._frames else None, width=34)
        if self._frames:
            self.spinner.pack(side="left", padx=(0, 12))
        label(cabecera, title, 16, "bold", anchor="w").pack(side="left", fill="x")
        self.status = label(body, t("starting"), 13, color="muted", anchor="w", justify="left", wraplength=360, width=360)
        self.status.pack(fill="x", pady=(4, 12))
        self.bar = ctk.CTkProgressBar(body, width=360, height=8, corner_radius=4, progress_color=C["accent"], fg_color=C["surface_alt"])
        self.bar.pack(fill="x")
        self.bar.set(0)
        self.cancel_btn = None
        if cancellable:
            self.cancel_btn = button(body, t("cancel"), variant="secondary", width=110, command=self.request_cancel)
            self.cancel_btn.pack(anchor="e", pady=(16, 0))

        center_on_parent(parent, self)
        make_modal(parent, self)
        self._spin()

    def _spin(self):
        if not self._frames or not self.winfo_exists():
            return
        self._frame = (self._frame + 1) % len(self._frames)
        self.spinner.configure(image=self._frames[self._frame])
        self.after(45, self._spin)

    def update_status(self, message, is_error=False, progress=None):
        if not self.winfo_exists():
            return
        self.status.configure(text=message, text_color=C["danger"] if is_error else C["muted"])
        if progress is not None:
            self.bar.set(progress)

    def request_cancel(self):
        self.cancel_event.set()
        self.status.configure(text=t("cancelling"), text_color=C["muted"])
        if self.cancel_btn is not None:
            set_enabled(self.cancel_btn, False)

    def close(self):
        if self.winfo_exists():
            try:
                self.grab_release()
            except tkinter.TclError:
                pass
            self.destroy()


class Toast(ctk.CTkFrame):
    """Aviso no bloqueante en la esquina superior derecha."""
    KINDS = {"success": ("check", "success"), "info": ("info", "accent"), "error": ("error", "danger")}

    def __init__(self, parent, message, kind="success", action=None, on_close=None):
        nombre_icono, color = self.KINDS.get(kind, self.KINDS["info"])
        super().__init__(parent, corner_radius=12, fg_color=C["surface"], border_width=1, border_color=C[color])
        self.on_close = on_close
        ctk.CTkLabel(self, text="", image=icon(nombre_icono, 20, color)).pack(side="left", padx=(14, 10), pady=12)
        label(self, message, 13, wraplength=260, justify="left", anchor="w").pack(side="left", pady=12)
        button(self, icon_name="close", variant="ghost", size="sm", command=self.close).pack(side="right", padx=(6, 8))
        if action:
            texto, callback = action

            def ejecutar():
                self.close()
                callback()
            button(self, texto, variant="primary", size="sm", command=ejecutar).pack(side="right", padx=(12, 0))

    def close(self):
        if self.winfo_exists():
            self.destroy()
        if self.on_close:
            self.on_close(self)


class Tooltip:
    def __init__(self, widget, text, delay=450):
        self.widget, self.text, self.delay = widget, text, delay
        self._job = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, event=None):
        self._cancel()
        self._job = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None

    def _show(self):
        self._job = None
        if self._tip or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_pointerx() + 12
        y = self.widget.winfo_pointery() + 18
        self._tip = tip = tkinter.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.attributes("-topmost", True)
        tkinter.Label(tip, text=self.text, bg=resolve(C["text"]), fg=resolve(C["surface"]),
                      font=(theme.font_family(), 9), padx=8, pady=4, justify="left", wraplength=280).pack()
        tip.wm_geometry(f"+{x}+{y}")

    def _hide(self, event=None):
        self._cancel()
        if self._tip:
            self._tip.destroy()
            self._tip = None


class StepIndicator(ctk.CTkFrame):
    """Indicador horizontal de pasos: ① → ② → ③."""

    def __init__(self, master, steps):
        super().__init__(master, fg_color="transparent")
        self.circles, self.labels = [], []
        for i, texto in enumerate(steps):
            if i:
                linea = ctk.CTkFrame(self, height=2, fg_color=C["border"])
                linea.pack(side="left", fill="x", expand=True, padx=10)
            # CTkButton (sin acción) respeta el tamaño exacto; un CTkLabel se estira con el texto
            circulo = ctk.CTkButton(self, text=str(i + 1), width=24, height=24, corner_radius=12, font=font(12, "bold"),
                                    hover=False, border_spacing=0)
            circulo.pack(side="left")
            etiqueta = label(self, texto, 13)
            etiqueta.pack(side="left", padx=(8, 0))
            self.circles.append(circulo)
            self.labels.append(etiqueta)
        self.set_state(set(), 0)

    def set_state(self, done, active):
        for i, (circulo, etiqueta) in enumerate(zip(self.circles, self.labels)):
            if i in done:
                circulo.configure(text="✓", fg_color=C["success"], text_color=C["on_accent"])
                etiqueta.configure(text_color=C["text"], font=font(13))
            elif i == active:
                circulo.configure(text=str(i + 1), fg_color=C["accent"], text_color=C["on_accent"])
                etiqueta.configure(text_color=C["text"], font=font(13, "bold"))
            else:
                circulo.configure(text=str(i + 1), fg_color=C["surface_alt"], text_color=C["muted"])
                etiqueta.configure(text_color=C["muted"], font=font(13))


# ----------------------------------------------------
# Tira de miniaturas (Canvas de Tk, se dibuja solo lo visible)
# ----------------------------------------------------
class ThumbnailStrip(ctk.CTkFrame):
    THUMB_W, THUMB_H, GAP, PAD = 54, 72, 10, 8

    def __init__(self, master, on_select):
        super().__init__(master, fg_color="transparent")
        self.on_select = on_select
        s = self._scaling()
        self.canvas = tkinter.Canvas(self, height=int((self.THUMB_H + 36) * s), highlightthickness=0, bd=0,
                                     bg=resolve(C["surface"]), xscrollincrement=int((self.THUMB_W + self.GAP) * s))
        self.scrollbar = ctk.CTkScrollbar(self, orientation="horizontal", command=self.canvas.xview, height=12,
                                          button_color=C["border"], button_hover_color=C["faint"])
        self.canvas.configure(xscrollcommand=self._on_xscroll)
        self.canvas.pack(fill="x")
        self.scrollbar.pack(fill="x")

        self.doc = None
        self.total = 0
        self.images = {}
        self.colors = {}
        self.excluded = set()
        self.rotations = {}
        self.matches = set()
        self.current = 0
        self._render_job = None
        self._redraw_job = None
        self._last_view = None
        self._scrollregion = None

        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Configure>", lambda e: self._schedule_redraw())

    def _scaling(self):
        return ctk.ScalingTracker.get_widget_scaling(self)

    def _metrics(self):
        s = self._scaling()
        return round(self.THUMB_W * s), round(self.THUMB_H * s), round(self.GAP * s), round(self.PAD * s), s

    def set_document(self, doc):
        self.doc = doc
        self.total = doc.page_count if doc else 0
        self.images.clear()
        self.current = 0
        self.canvas.xview_moveto(0)
        self.redraw()

    def set_marks(self, colors=None, excluded=None, rotations=None, matches=None):
        if matches is not None:
            self.matches = matches
        if colors is not None:
            self.colors = colors
        if excluded is not None:
            self.excluded = excluded
        if rotations is not None:
            self.rotations = rotations
        self.redraw()

    def set_current(self, index):
        self.current = index
        self._ensure_visible(index)
        self.redraw()

    def invalidate(self, index):
        self.images.pop(index, None)
        self.redraw()

    def refresh_theme(self):
        self.canvas.configure(bg=resolve(C["surface"]))
        self.redraw()

    def _visible_range(self):
        tw, th, gap, pad, _ = self._metrics()
        paso = tw + gap
        x0 = self.canvas.canvasx(0)
        x1 = self.canvas.canvasx(max(1, self.canvas.winfo_width()))
        primero = max(0, int((x0 - pad) // paso) - 2)
        ultimo = min(self.total - 1, int((x1 - pad) // paso) + 2)
        return primero, ultimo

    def _schedule_redraw(self):
        if self._redraw_job is None:
            self._redraw_job = self.after(16, self.redraw)

    def redraw(self):
        self._redraw_job = None
        c = self.canvas
        c.delete("all")
        tw, th, gap, pad, s = self._metrics()
        alto = int(c.cget("height"))
        ancho_total = max(1, pad * 2 + self.total * (tw + gap) - gap)
        region = (0, 0, ancho_total, alto)
        if region != self._scrollregion:
            self._scrollregion = region
            c.configure(scrollregion=region)
        if not self.total:
            return

        fondo, borde = resolve(C["surface_alt"]), resolve(C["border"])
        acento, tenue, peligro = resolve(C["accent"]), resolve(C["muted"]), resolve(C["danger"])
        fuente = (theme.font_family(), -max(9, int(11 * s)))
        primero, ultimo = self._visible_range()
        faltan = False
        for i in range(primero, ultimo + 1):
            x, y = pad + i * (tw + gap), pad
            imagen = self.images.get(i)
            if imagen is not None:
                c.create_image(x + tw / 2, y + th / 2, image=imagen)
                # Borde sutil para que las páginas blancas se distingan en modo claro
                iw, ih = imagen.width(), imagen.height()
                c.create_rectangle(x + (tw - iw) / 2, y + (th - ih) / 2, x + (tw + iw) / 2, y + (th + ih) / 2,
                                   outline=borde, width=1)
            else:
                c.create_rectangle(x, y, x + tw, y + th, fill=fondo, outline="")
                faltan = True
            if i in self.excluded:
                c.create_rectangle(x, y, x + tw, y + th, outline=peligro, width=2)
                c.create_line(x + 8, y + 8, x + tw - 8, y + th - 8, fill=peligro, width=3)
                c.create_line(x + tw - 8, y + 8, x + 8, y + th - 8, fill=peligro, width=3)
            if i in self.matches:
                # Punto en la esquina: la página contiene el texto buscado
                r = max(4, int(5 * s))
                c.create_oval(x + tw - 2 * r - 2, y + 2, x + tw - 2, y + 2 * r + 2, fill=resolve(C["warning"]), outline="")
            if i == self.current:
                c.create_rectangle(x - 3, y - 3, x + tw + 3, y + th + 3, outline=acento, width=2)
            color = self.colors.get(i)
            if color:
                c.create_rectangle(x, y + th + int(6 * s), x + tw, y + th + int(10 * s), fill=color, outline="")
            c.create_text(x + tw / 2, y + th + int(22 * s), text=str(i + 1), font=fuente,
                          fill=acento if i == self.current else tenue)
        if faltan:
            self._schedule_render()

    def _schedule_render(self):
        if self._render_job is None and self.doc is not None:
            self._render_job = self.after(30, self._render_some)

    def _render_some(self):
        self._render_job = None
        if self.doc is None:
            return
        tw, th, *_ = self._metrics()
        primero, ultimo = self._visible_range()
        renderizadas = 0
        for i in range(primero, ultimo + 1):
            if i in self.images:
                continue
            try:
                pagina = self.doc.load_page(i)
                rot = self.rotations.get(i, 0)
                ancho, alto = (pagina.rect.height, pagina.rect.width) if rot % 180 else (pagina.rect.width, pagina.rect.height)
                zoom = min(tw / ancho, th / alto)
                pix = pagina.get_pixmap(matrix=fitz.Matrix(zoom, zoom).prerotate(rot), alpha=False)
                self.images[i] = ImageTk.PhotoImage(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
            except Exception:
                # Página que no se puede renderizar: se muestra un recuadro vacío
                self.images[i] = ImageTk.PhotoImage(Image.new("RGB", (tw, th), resolve(C["surface_alt"])))
            renderizadas += 1
            if renderizadas >= 4:
                break
        if renderizadas:
            self.redraw()

    def _on_xscroll(self, first, last):
        self.scrollbar.set(first, last)
        vista = (first, last)
        if vista != self._last_view:
            self._last_view = vista
            self._schedule_redraw()

    def _ensure_visible(self, index):
        tw, th, gap, pad, _ = self._metrics()
        x = pad + index * (tw + gap)
        izquierda = self.canvas.canvasx(0)
        ancho_vista = self.canvas.winfo_width()
        if x < izquierda or x + tw > izquierda + ancho_vista:
            ancho_total = max(1, pad * 2 + self.total * (tw + gap) - gap)
            self.canvas.xview_moveto(max(0, x - (ancho_vista - tw) / 2) / ancho_total)

    def _on_click(self, event):
        tw, th, gap, pad, _ = self._metrics()
        x = self.canvas.canvasx(event.x)
        i = int((x - pad) // (tw + gap))
        if 0 <= i < self.total:
            self.on_select(i)

    def _on_wheel(self, event):
        self.canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")


# ----------------------------------------------------
# Lista de archivos PDF (para Unir y Lote)
# ----------------------------------------------------
class FileList(ctk.CTkFrame):
    def __init__(self, master, app, on_change=None, reorderable=True,
                 empty_text=None):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.on_change = on_change
        self.reorderable = reorderable
        self.items = []

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=C["input"], corner_radius=10, border_width=1,
                                             border_color=C["border"], scrollbar_button_color=C["border"])
        self.scroll.pack(fill="both", expand=True)
        self.empty_label = label(self.scroll, empty_text or t("filelist_empty"), 13, color="faint", justify="center")
        self.empty_label.pack(pady=40)

    def add_files(self, paths):
        invalidos = []
        existentes = {os.path.normcase(os.path.abspath(i["path"])) for i in self.items}
        for ruta in paths:
            if not ruta.lower().endswith(".pdf"):
                invalidos.append(os.path.basename(ruta))
                continue
            clave = os.path.normcase(os.path.abspath(ruta))
            if clave in existentes:
                continue
            try:
                doc = self.app.open_fitz(ruta)  # Pide la contraseña si el PDF está protegido
            except Exception:
                invalidos.append(os.path.basename(ruta))
                continue
            if doc is None:
                continue  # El usuario canceló la contraseña
            paginas = doc.page_count
            doc.close()
            existentes.add(clave)
            self._add_row(ruta, paginas)
        self._refresh()
        if invalidos:
            Dialog.alert(self.app, t("filelist_invalid_title"), t("filelist_invalid_message"), detail="\n".join(invalidos))

    def _add_row(self, ruta, paginas):
        fila = ctk.CTkFrame(self.scroll, fg_color=C["surface"], corner_radius=8, border_width=1, border_color=C["border"])
        item = {"path": ruta, "pages": paginas, "frame": fila}

        protegido = self.app.password_for(ruta) is not None
        ctk.CTkLabel(fila, text="", image=icon("lock" if protegido else "file", 18, "accent")).pack(side="left", padx=(10, 8), pady=8)
        textos = ctk.CTkFrame(fila, fg_color="transparent")
        textos.pack(side="left", fill="x", expand=True, pady=6)
        label(textos, os.path.basename(ruta), 13, "bold", anchor="w").pack(fill="x")
        try:
            tamano = formatear_tamano(os.path.getsize(ruta))
        except OSError:
            tamano = "?"
        label(textos, f"{t('pages_count', n=paginas)} · {tamano}", 11, color="muted", anchor="w").pack(fill="x")

        button(fila, icon_name="close", variant="danger_ghost", size="sm", tooltip=t("remove"),
               command=lambda: self.remove(item)).pack(side="right", padx=(2, 8))
        if self.reorderable:
            button(fila, icon_name="down", variant="ghost", size="sm", tooltip=t("move_down"),
                   command=lambda: self.move(item, 1)).pack(side="right", padx=2)
            button(fila, icon_name="up", variant="ghost", size="sm", tooltip=t("move_up"),
                   command=lambda: self.move(item, -1)).pack(side="right", padx=2)
        self.items.append(item)
        self.app.enable_drop(fila)

    def remove(self, item):
        item["frame"].destroy()
        self.items.remove(item)
        self._refresh()

    def move(self, item, delta):
        i = self.items.index(item)
        j = i + delta
        if 0 <= j < len(self.items):
            self.items[i], self.items[j] = self.items[j], self.items[i]
            self._refresh()

    def clear(self):
        for item in self.items:
            item["frame"].destroy()
        self.items.clear()
        self._refresh()

    def _refresh(self):
        for item in self.items:
            item["frame"].pack_forget()
        if self.items:
            self.empty_label.pack_forget()
            for item in self.items:
                item["frame"].pack(fill="x", padx=6, pady=3)
        else:
            self.empty_label.pack(pady=40)
        if self.on_change:
            self.on_change()

    def paths(self):
        return [i["path"] for i in self.items]

    def total_pages(self):
        return sum(i["pages"] for i in self.items)
