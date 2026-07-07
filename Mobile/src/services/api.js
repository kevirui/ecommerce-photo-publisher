import axios from 'axios';
import * as FileSystem from 'expo-file-system';

// Cambia esta IP por la IP local de tu notebook en el WiFi (ej. 192.168.1.50)
const BASE_URL = 'http://192.168.1.42:8000/api/v1';

export const getPendingProducts = async () => {
  try {
    const response = await axios.get(`${BASE_URL}/articles/pending`, {
      timeout: 15000,
    });
    return response.data.articles;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || 'Error en el servidor');
    } else if (error.request) {
      throw new Error('No se pudo conectar al servidor. Verifica la IP y conexión.');
    } else {
      throw new Error('Error al obtener los artículos pendientes.');
    }
  }
};

export const uploadPhoto = async (photoUri, articleCode, includeStamp, imageIndex = 0, watermarkOpacity = 0.3) => {
  try {
    const formData = new FormData();

    // Extraer el nombre y tipo del archivo
    const filename = photoUri.split('/').pop() || 'photo.jpg';
    const match = /\.(\w+)$/.exec(filename);
    const type = match ? `image/${match[1]}` : `image`;

    formData.append('file', {
      uri: photoUri,
      name: filename,
      type,
    });

    formData.append('article_code', articleCode);
    formData.append('include_stamp', includeStamp ? 'true' : 'false');
    formData.append('image_index', imageIndex.toString());
    formData.append('watermark_opacity', watermarkOpacity.toString());

    const response = await axios.post(`${BASE_URL}/photos/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 30000, // 30 segundos
    });

    return response.data;
  } catch (error) {
    if (error.response) {
      // El servidor respondió con un estado de error
      throw new Error(error.response.data.error || 'Error en el servidor');
    } else if (error.request) {
      // La petición fue hecha pero no hubo respuesta
      throw new Error('No se pudo conectar al servidor. Verifica la IP y conexión.');
    } else {
      throw new Error('Error al preparar la subida de la imagen.');
    }
  }
};

export const getPendingProductsFromExcel = async (fileUri) => {
  try {
    const url = `${BASE_URL}/articles/pending/from-excel`;
    console.log('Uploading Excel via FileSystem.uploadAsync to:', url, 'URI:', fileUri);

    const result = await FileSystem.uploadAsync(url, fileUri, {
      httpMethod: 'POST',
      uploadType: FileSystem.FileSystemUploadType.MULTIPART,
      fieldName: 'file',
    });

    console.log('Upload response status:', result.status);

    if (result.status < 200 || result.status >= 300) {
      let detail = `Error en el servidor (${result.status})`;
      try {
        const parsed = JSON.parse(result.body);
        if (parsed.detail) detail = parsed.detail;
      } catch (_) {}
      throw new Error(detail);
    }

    const data = JSON.parse(result.body);
    return data.articles;
  } catch (error) {
    console.error('getPendingProductsFromExcel Error:', error);
    throw new Error(error.message || 'Error al enviar el archivo Excel.');
  }
};
