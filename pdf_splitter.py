import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from pypdf import PdfReader, PdfWriter
import threading
import fitz  # PyMuPDF
from PIL import Image

def dividir_pdf_por_capitulos(ruta_pdf, estructura_capitulos, carpeta_salida, callback_log=None):
    """
    Divide un archivo PDF en múltiples archivos según los rangos de páginas especificados.
    """
    def log(mensaje, is_error=False, progress=None):
        if callback_log:
            callback_log(mensaje, is_error, progress)

    if not os.path.exists(ruta_pdf):
        log("Error: No se encontró el archivo original.", True)
        return False

    if not os.path.exists(carpeta_salida):
        os.makedirs(carpeta_salida)
        log(f"Carpeta '{carpeta_salida}' creada para guardar los PDFs.")

    log("Leyendo el archivo original...")
    try:
        lector = PdfReader(ruta_pdf)
        total_paginas_pdf = len(lector.pages)
    except Exception as e:
        log(f"Error al leer el PDF: {e}", True)
        return False

    total_capitulos = len(estructura_capitulos)
    for idx, (nombre_capitulo, pag_inicio, pag_fin) in enumerate(estructura_capitulos):
        if pag_inicio < 1 or pag_fin > total_paginas_pdf or pag_inicio > pag_fin:
            log(f"Error en rango para '{nombre_capitulo}' (total pags: {total_paginas_pdf}).", True)
            continue

        escritor = PdfWriter()
        
        for num_pagina in range(pag_inicio - 1, pag_fin):
            escritor.add_page(lector.pages[num_pagina])
            
        nombre_archivo_salida = f"{nombre_capitulo.replace(' ', '_')}.pdf"
        ruta_salida = os.path.join(carpeta_salida, nombre_archivo_salida)
        
        with open(ruta_salida, 'wb') as archivo_salida:
            escritor.write(archivo_salida)
            
        log(f"Procesando: {nombre_archivo_salida}", progress=(idx + 1) / total_capitulos)
        
    log("¡Proceso completado exitosamente!", progress=1.0)
    return True

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("PDF Splitter Pro")
        self.geometry("1150x700")
        self.minsize(950, 600)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Tipografía moderna por defecto en Windows
        self.font_family = "Segoe UI"
        
        self.pdf_path = ""
        self.dest_path = ""
        self.chapter_rows = []
        
        # Estado del visor PDF
        self.pdf_doc = None
        self.current_preview_page = 0
        self.total_pages = 0
        self.current_ctk_image = None
        
        self.create_widgets()
        
    def show_custom_alert(self, title, message, is_error=False):
        alert = ctk.CTkToplevel(self)
        alert.title(title)
        alert.geometry("400x180")
        alert.resizable(False, False)
        alert.attributes("-topmost", True)
        alert.grab_set()
        
        # Center the alert
        alert.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (400 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (180 // 2)
        alert.geometry(f"+{x}+{y}")
        
        color = "#EF4444" if is_error else "#10B981"
        icon_text = "❌" if is_error else "✓"
        
        lbl_icon = ctk.CTkLabel(alert, text=icon_text, font=ctk.CTkFont(size=35, weight="bold"), text_color=color, justify="center")
        lbl_icon.pack(pady=(15, 5), anchor="center")
        
        lbl_msg = ctk.CTkLabel(alert, text=message, font=ctk.CTkFont(family=self.font_family, size=14))
        lbl_msg.pack(pady=5)
        
        btn = ctk.CTkButton(alert, text="Aceptar", width=120, command=alert.destroy, fg_color="#3B82F6", hover_color="#2563EB", font=ctk.CTkFont(family=self.font_family, weight="bold"))
        btn.pack(pady=(10, 15))

    def create_widgets(self):
        # Contenedor principal que dividirá en dos columnas
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Panel Izquierdo (Controles Actuales)
        self.left_panel = ctk.CTkFrame(self.main_container, fg_color="transparent", width=450)
        self.left_panel.pack_propagate(False)
        self.left_panel.pack(side="left", fill="y", padx=(0, 10))
        
        # Header
        self.header_label = ctk.CTkLabel(self.left_panel, text="PDF Splitter", font=ctk.CTkFont(family=self.font_family, size=28, weight="bold"))
        self.header_label.pack(pady=(5, 5))
        
        self.sub_label = ctk.CTkLabel(self.left_panel, text="Divide tus PDF de forma rápida y sencilla.", font=ctk.CTkFont(family=self.font_family, size=15), text_color="#A0A0A0")
        self.sub_label.pack(pady=(0, 25))
        
        # Paths Frame
        self.paths_frame = ctk.CTkFrame(self.left_panel, corner_radius=15, fg_color="#1E1E1E")
        self.paths_frame.pack(fill="x", pady=10)
        
        # PDF Selection
        self.pdf_btn = ctk.CTkButton(self.paths_frame, text="📄 Buscar PDF", command=self.select_pdf, font=ctk.CTkFont(family=self.font_family, weight="bold"), corner_radius=8, fg_color="#3B82F6", hover_color="#2563EB")
        self.pdf_btn.grid(row=0, column=0, padx=15, pady=15)
        self.pdf_label = ctk.CTkLabel(self.paths_frame, text="Ningún archivo seleccionado", text_color="#A0A0A0", font=ctk.CTkFont(family=self.font_family, slant="italic"))
        self.pdf_label.grid(row=0, column=1, padx=10, pady=15, sticky="w")
        
        # Destination Selection
        self.dest_btn = ctk.CTkButton(self.paths_frame, text="📁 Carpeta Destino", command=self.select_dest, font=ctk.CTkFont(family=self.font_family, weight="bold"), corner_radius=8, fg_color="#3B82F6", hover_color="#2563EB")
        self.dest_btn.grid(row=1, column=0, padx=15, pady=15)
        self.dest_label = ctk.CTkLabel(self.paths_frame, text="Ninguna carpeta seleccionada", text_color="#A0A0A0", font=ctk.CTkFont(family=self.font_family, slant="italic"))
        self.dest_label.grid(row=1, column=1, padx=10, pady=15, sticky="w")
        
        # Chapters Section
        self.chapters_label = ctk.CTkLabel(self.left_panel, text="Configuración de Capítulos", font=ctk.CTkFont(family=self.font_family, size=18, weight="bold"))
        self.chapters_label.pack(pady=(25, 5), anchor="w")
        
        # Scrollable Frame for Chapters
        self.scrollable_frame = ctk.CTkScrollableFrame(self.left_panel, height=220, corner_radius=15, fg_color="#1E1E1E")
        self.scrollable_frame.pack(fill="both", expand=True, pady=5)
        
        # Header for columns
        self.header_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(5, 10))
        ctk.CTkLabel(self.header_frame, text="Nombre del Capítulo", width=180, anchor="w", font=ctk.CTkFont(family=self.font_family, weight="bold", size=13), text_color="#888888").pack(side="left", padx=5)
        ctk.CTkLabel(self.header_frame, text="Inicio", width=60, anchor="w", font=ctk.CTkFont(family=self.font_family, weight="bold", size=13), text_color="#888888").pack(side="left", padx=5)
        ctk.CTkLabel(self.header_frame, text="Fin", width=60, anchor="w", font=ctk.CTkFont(family=self.font_family, weight="bold", size=13), text_color="#888888").pack(side="left", padx=5)
        
        self.add_chapter_btn = ctk.CTkButton(self.left_panel, text="➕ Agregar Capítulo", command=self.add_chapter_row, fg_color="transparent", border_width=1, border_color="#3B82F6", text_color="#3B82F6", hover_color="#2A2A2A", corner_radius=8, font=ctk.CTkFont(family=self.font_family, weight="bold"))
        self.add_chapter_btn.pack(pady=15)
        
        # Initial row
        self.add_chapter_row()
        
        # Execute Button
        self.execute_btn = ctk.CTkButton(self.left_panel, text="✂️ Dividir PDF", command=self.process_pdf, height=45, width=250, font=ctk.CTkFont(family=self.font_family, size=16, weight="bold"), corner_radius=10, fg_color="#10B981", hover_color="#059669")
        self.execute_btn.pack(pady=(10, 5))
        
        # ----------------------------------------------------
        # Panel Derecho (Previsualizador de PDF)
        # ----------------------------------------------------
        self.right_panel = ctk.CTkFrame(self.main_container, corner_radius=15, fg_color="#1A1A1A")
        self.right_panel.pack(side="right", fill="both", expand=True, padx=(30, 0))
        
        self.preview_title = ctk.CTkLabel(self.right_panel, text="Previsualizador", font=ctk.CTkFont(family=self.font_family, size=18, weight="bold"), text_color="#E0E0E0")
        self.preview_title.pack(pady=(20, 10))
        
        # Marco de imagen (fondo gris muy oscuro para simular canvas)
        self.image_container = ctk.CTkFrame(self.right_panel, fg_color="#0F0F0F", corner_radius=10)
        self.image_container.pack(fill="both", expand=True, padx=20, pady=5)
        
        self.preview_image_label = ctk.CTkLabel(self.image_container, text="Abre un PDF para visualizarlo aquí", text_color="#555555", font=ctk.CTkFont(family=self.font_family, slant="italic"))
        self.preview_image_label.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Bind resize para que la imagen escale al maximizar
        self.image_container.bind("<Configure>", self.on_resize)
        
        # Controles inferiores del previsualizador
        self.preview_controls = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.preview_controls.pack(fill="x", pady=(10, 20), padx=20)
        
        self.prev_btn = ctk.CTkButton(self.preview_controls, text="◀ Anterior", width=100, command=self.prev_page, state="disabled", fg_color="#333333", hover_color="#444444", text_color="#FFFFFF")
        self.prev_btn.pack(side="left", padx=10)
        
        self.page_indicator_label = ctk.CTkLabel(self.preview_controls, text="Página - de -", font=ctk.CTkFont(family=self.font_family, weight="bold"))
        self.page_indicator_label.pack(side="left", expand=True)
        
        self.next_btn = ctk.CTkButton(self.preview_controls, text="Siguiente ▶", width=100, command=self.next_page, state="disabled", fg_color="#333333", hover_color="#444444", text_color="#FFFFFF")
        self.next_btn.pack(side="right", padx=10)
        
        # Binds para flechas direccionales
        self.bind("<Right>", lambda event: self.next_page() if self.next_btn.cget("state") == "normal" else None)
        self.bind("<Left>", lambda event: self.prev_page() if self.prev_btn.cget("state") == "normal" else None)
        
    def on_resize(self, event):
        if hasattr(self, '_resize_timer'):
            self.after_cancel(self._resize_timer)
        self._resize_timer = self.after(200, self.update_preview_image)
        
    def select_pdf(self):
        filepath = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if filepath:
            self.pdf_path = filepath
            self.pdf_label.configure(text=os.path.basename(filepath), text_color=("black", "white"))
            self.load_pdf_preview(filepath)
            
    def load_pdf_preview(self, filepath):
        try:
            if self.pdf_doc:
                self.pdf_doc.close()
                
            self.pdf_doc = fitz.open(filepath)
            self.total_pages = len(self.pdf_doc)
            self.current_preview_page = 0
            
            self.update_preview_image()
            
        except Exception as e:
            self.show_custom_alert("Error de visualización", f"No se pudo cargar la vista previa: {e}", is_error=True)
            self.pdf_doc = None
            self.preview_image_label.configure(image="", text="Error al cargar la previsualización")
            self.page_indicator_label.configure(text="Página - de -")
            self.prev_btn.configure(state="disabled")
            self.next_btn.configure(state="disabled")

    def update_preview_image(self):
        if not self.pdf_doc:
            return
            
        page = self.pdf_doc.load_page(self.current_preview_page)
        # Convertir a imagen RGB (escalado 2x para nitidez)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0)) 
        mode = "RGBA" if pix.alpha else "RGB"
        img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        
        w, h = img.size
        
        # Dimensiones dinámicas basadas en el contenedor
        self.image_container.update_idletasks()
        max_width = self.image_container.winfo_width() - 20
        max_height = self.image_container.winfo_height() - 20
        
        if max_width < 100: max_width = 450
        if max_height < 100: max_height = 500
        
        ratio = min(max_width/w, max_height/h)
        new_size = (int(w*ratio), int(h*ratio))
        
        self.current_ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=new_size)
        self.preview_image_label.configure(image=self.current_ctk_image, text="")
        
        # Actualizar indicador
        self.page_indicator_label.configure(text=f"Página {self.current_preview_page + 1} de {self.total_pages}")
        
        # Botones
        self.prev_btn.configure(state="normal" if self.current_preview_page > 0 else "disabled")
        self.next_btn.configure(state="normal" if self.current_preview_page < self.total_pages - 1 else "disabled")

    def prev_page(self):
        if self.current_preview_page > 0:
            self.current_preview_page -= 1
            self.update_preview_image()
            
    def next_page(self):
        if self.pdf_doc and self.current_preview_page < self.total_pages - 1:
            self.current_preview_page += 1
            self.update_preview_image()
            
    def select_dest(self):
        folderpath = filedialog.askdirectory()
        if folderpath:
            self.dest_path = folderpath
            self.dest_label.configure(text=folderpath, text_color=("black", "white"))
            
    def add_chapter_row(self):
        row_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=5)
        
        name_entry = ctk.CTkEntry(row_frame, width=180, placeholder_text="Ej: Introducción", font=ctk.CTkFont(family=self.font_family), corner_radius=6, border_color="#333333")
        name_entry.pack(side="left", padx=5)
        
        start_entry = ctk.CTkEntry(row_frame, width=60, placeholder_text="Pág", font=ctk.CTkFont(family=self.font_family), corner_radius=6, border_color="#333333")
        start_entry.pack(side="left", padx=5)
        
        end_entry = ctk.CTkEntry(row_frame, width=60, placeholder_text="Pág", font=ctk.CTkFont(family=self.font_family), corner_radius=6, border_color="#333333")
        end_entry.pack(side="left", padx=5)
        
        row_data = {"frame": row_frame, "name": name_entry, "start": start_entry, "end": end_entry}
        
        def remove_row():
            row_frame.destroy()
            if row_data in self.chapter_rows:
                self.chapter_rows.remove(row_data)
                
        remove_btn = ctk.CTkButton(row_frame, text="✖", width=35, fg_color="#EF4444", hover_color="#DC2626", corner_radius=6, command=remove_row, font=ctk.CTkFont(weight="bold"))
        remove_btn.pack(side="left", padx=10)
        
        self.chapter_rows.append(row_data)

    def process_pdf(self):
        if not self.pdf_path:
            self.show_custom_alert("Falta archivo", "Por favor selecciona el archivo PDF original.", is_error=True)
            return
        if not self.dest_path:
            self.show_custom_alert("Falta destino", "Por favor selecciona la carpeta de destino.", is_error=True)
            return
            
        estructura = []
        for row in self.chapter_rows:
            name = row["name"].get().strip()
            start = row["start"].get().strip()
            end = row["end"].get().strip()
            
            if not name and not start and not end:
                continue
                
            if not name or not start or not end:
                self.show_custom_alert("Fila incompleta", "Hay filas incompletas. Por favor complétalas o elimínalas.", is_error=True)
                return
                
            try:
                estructura.append((name, int(start), int(end)))
            except ValueError:
                self.show_custom_alert("Error", f"Las páginas deben ser números enteros (revisa '{name}').", is_error=True)
                return
                
        if not estructura:
            self.show_custom_alert("Falta estructura", "Debes agregar al menos un capítulo válido.", is_error=True)
            return
            
        self.execute_btn.configure(state="disabled", text="⏳ Procesando...")
        
        # Modal Alert Window for Loading
        progress_window = ctk.CTkToplevel(self)
        progress_window.title("Procesando...")
        progress_window.geometry("400x150")
        progress_window.resizable(False, False)
        progress_window.attributes("-topmost", True)
        progress_window.grab_set() # Block interaction with main window
        
        # Center the toplevel window
        progress_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (400 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (150 // 2)
        progress_window.geometry(f"+{x}+{y}")
        
        lbl_status = ctk.CTkLabel(progress_window, text="Iniciando proceso...", font=ctk.CTkFont(family=self.font_family, size=14, weight="bold"))
        lbl_status.pack(pady=(25, 10))
        
        progress_bar = ctk.CTkProgressBar(progress_window, width=300, corner_radius=8, progress_color="#10B981")
        progress_bar.pack(pady=10)
        progress_bar.set(0)
        
        def log_callback(msg, is_error=False, progress=None):
            def update_ui():
                if is_error:
                    lbl_status.configure(text=msg, text_color="#EF4444")
                else:
                    lbl_status.configure(text=msg, text_color="white")
                if progress is not None:
                    progress_bar.set(progress)
            self.after(0, update_ui)
            
        def worker():
            exito = dividir_pdf_por_capitulos(self.pdf_path, estructura, self.dest_path, callback_log=log_callback)
            
            def on_finish():
                self.execute_btn.configure(state="normal", text="✂️ Dividir PDF")
                progress_window.destroy()
                if exito:
                    # Mostrar alerta moderna de completado
                    self.show_custom_alert("¡Éxito!", "El PDF se dividió en secciones correctamente.", is_error=False)
            
            self.after(500, on_finish) # Pequeño delay visual
            
        threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    app = App()
    app.mainloop()