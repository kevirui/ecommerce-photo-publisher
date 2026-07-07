# Mobile App - Ecommerce Photo Capturer

Aplicación móvil híbrida desarrollada con **React Native** y **Expo** para la captura rápida y directa de fotos de artículos e-commerce.

## Funciones Principales

- **Interfaz Simple**: Flujo directo de inicio para toma de fotos rápidas.
- **Captura con Cámara**: Integración nativa con la cámara del dispositivo (`expo-camera`).
- **Vista de Carga (Upload)**: Permite ingresar el código del artículo, ajustar parámetros adicionales (como la opacidad del sello/marca de agua y si se incluye un sello o no) antes de subir la imagen.
- **Validación & Estado de Pendientes**: Mantiene una lista de artículos pendientes de procesar/subir para organizar el flujo del operador físico.
- **Subida Directa**: Envía de forma inalámbrica la foto capturada al endpoint del Backend.

---

## Requisitos de Instalación

1. **Node.js LTS**: Asegúrate de tener instalado Node.js en tu equipo.
2. **Expo Go**: Descarga la aplicación *Expo Go* en tu dispositivo móvil (disponible para Android en la Play Store y iOS en la App Store) para correr la app de forma inalámbrica.

---

## Configuración y Ejecución

1. **Instalar dependencias**:
   ```bash
   npm install
   ```

2. **Iniciar el Servidor Expo**:
   ```bash
   npm run start
   ```
   *O alternativamente `npx expo start`.*

3. **Ejecutar en tu dispositivo**:
   - Escanea el código QR generado en la terminal utilizando la aplicación de cámara de tu iPhone o a través de la aplicación **Expo Go** en Android.
   - Asegúrate de que tanto tu computadora como tu dispositivo móvil estén conectados a la **misma red Wi-Fi**.

---

## Variables y URLs

La aplicación móvil se conecta al backend a través de peticiones HTTP. Asegúrate de configurar la URL correcta del backend local (generalmente tu dirección IP local `http://192.168.x.x:8000`) en la configuración del cliente HTTP (`axios` u otra librería) de la app para que pueda haber comunicación correcta en la red local.
