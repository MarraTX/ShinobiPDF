# Publicar en Microsoft Store

La versión de la Store es la misma app empaquetada como **MSIX**. Microsoft firma el paquete al publicarlo,
así que no hace falta un certificado de firma de código y Windows no muestra el aviso de SmartScreen.

Diferencias con el instalador (`ShinobiPDF-Setup.exe`):

* **Actualizaciones:** las instala la Store. La app no consulta GitHub y en *Ajustes* no aparece la sección
  de actualizaciones (las políticas de la Store no permiten que una app se actualice por su cuenta).
* **Menú contextual:** «Dividir con Shinobi.pdf» viene declarado en el manifiesto del paquete. Siempre está activo
  y se borra al desinstalar. En *Ajustes* se muestra como información, sin interruptor.
* **Idioma:** como no hay asistente de instalación, la primera vez se usa el idioma de Windows.
* **Preferencias:** Windows las guarda dentro del paquete y las borra al desinstalar.

## 1. Reservar el nombre (una sola vez)

1. Crear la cuenta de desarrollador individual en [Partner Center](https://partner.microsoft.com/dashboard/registration)
   (para personas es gratis).
2. *Apps y juegos → Nueva app → MSIX o PWA* y reservar el nombre **Shinobi.pdf**.
3. En *Administración de productos → Identidad del producto* copiar estos tres valores en
   [`installer/msix/store_identity.json`](../installer/msix/store_identity.json) y hacer commit:

   | Partner Center | `store_identity.json` |
   |---|---|
   | `Package/Identity/Name` | `identity_name` |
   | `Package/Identity/Publisher` | `publisher` (empieza con `CN=`) |
   | `Package/Properties/PublisherDisplayName` | `publisher_display_name` |

## 2. Generar el paquete

Lo genera GitHub Actions:

* En cada versión publicada (tag `v*`) el job *release* de CI deja el artefacto **ShinobiPDF-msix**.
* También se puede correr a mano el workflow **MSIX** desde la pestaña *Actions*.

O en tu PC (necesita el Windows SDK: `winget install Microsoft.WindowsSDK.10.0.26100`):

```
python tools/build_exe.py
python tools/build_msix.py      -> dist/ShinobiPDF.msix
```

La versión del paquete sale de `APP_VERSION` en `shinobi/__init__.py` (`1.2` → `1.2.0.0`).
La Store exige que cada envío tenga una versión mayor que el anterior.

### Probarlo en tu PC antes de subirlo

El `.msix` no está firmado, así que no se instala con doble clic. Para probarlo, activá el
*Modo de desarrollador* (Configuración → Sistema → Para programadores) y en PowerShell:

```
Add-AppxPackage -Register dist\msix\AppxManifest.xml
```

La app aparece en el menú Inicio como si viniera de la Store. Para quitarla:
`Get-AppxPackage *Shinobi* | Remove-AppxPackage`.

## 3. Enviar a la Store

En Partner Center → *Nuevo envío*:

* **Paquetes:** subir `ShinobiPDF.msix`.
* **Precio:** gratis.
* **Propiedades:** categoría *Productividad*. Si te pregunta por `runFullTrust`, explicá que es una app de
  escritorio Win32 (Python/Tkinter) que necesita leer y escribir los PDF que elige el usuario.
* **Clasificación por edades:** completar el cuestionario (no tiene contenido para adultos ni compras).
* **Ficha de la Store (inglés y español):** descripción, capturas (`docs/screenshot-en.png`, `docs/screenshot-es.png`)
  y la URL de la política de privacidad (la sección *Privacy policy* del README o la página de la web).

La revisión suele tardar entre unas horas y 3 días hábiles.
