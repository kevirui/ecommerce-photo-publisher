import React, { useState, useRef } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, SafeAreaView, ActivityIndicator } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';

export default function CameraScreen({ onPhotoTaken, onBack }) {
  const [permission, requestPermission] = useCameraPermissions();
  const [isTaking, setIsTaking] = useState(false);
  const [cameraKey, setCameraKey] = useState(0);
  const [flash, setFlash] = useState('off');
  const cameraRef = useRef(null);

  if (!permission) {
    // Los permisos aún se están cargando
    return <View style={styles.container} />;
  }

  if (!permission.granted) {
    // Permisos no otorgados
    return (
      <View style={styles.container}>
        <Text style={styles.text}>Necesitamos permiso para usar la cámara</Text>
        <TouchableOpacity style={styles.button} onPress={requestPermission}>
          <Text style={styles.buttonText}>Otorgar Permiso</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.button, styles.backButton]} onPress={onBack}>
          <Text style={styles.buttonText}>Volver</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const takePicture = async () => {
    if (cameraRef.current && !isTaking) {
      setIsTaking(true);
      try {
        const photo = await cameraRef.current.takePictureAsync({
          quality: 0.8, // Buena calidad pero no máxima para optimizar
          skipProcessing: true,
        });
        onPhotoTaken(photo.uri);
      } catch (error) {
        console.error("Error al tomar foto: ", error);
        alert("Hubo un error al capturar la imagen.");
      } finally {
        setIsTaking(false);
      }
    }
  };

  const handleRestartCamera = () => {
    setCameraKey(prev => prev + 1);
  };

  const toggleFlash = () => {
    setFlash(prev => {
      if (prev === 'off') return 'on';
      if (prev === 'on') return 'auto';
      return 'off';
    });
  };

  const getFlashLabel = () => {
    if (flash === 'on') return '⚡ On';
    if (flash === 'auto') return '⚡ Auto';
    return '⚡ Off';
  };

  return (
    <SafeAreaView style={styles.container}>
      <CameraView key={cameraKey} style={styles.camera} facing="back" flash={flash} ref={cameraRef}>
        <View style={styles.overlayContainer}>
          {/* Barra Superior */}
          <View style={styles.headerBar}>
            <TouchableOpacity style={styles.headerButton} onPress={onBack} activeOpacity={0.7}>
              <Text style={styles.headerButtonText}>✕ Volver</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.headerButton} onPress={toggleFlash} activeOpacity={0.7}>
              <Text style={styles.headerButtonText}>{getFlashLabel()}</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.headerButton} onPress={handleRestartCamera} activeOpacity={0.7}>
              <Text style={styles.headerButtonText}>🔄 Reiniciar</Text>
            </TouchableOpacity>
          </View>

          {/* Botón de captura inferior */}
          <View style={styles.buttonContainer}>
            <TouchableOpacity 
              style={styles.captureButton} 
              onPress={takePicture}
              disabled={isTaking}
              activeOpacity={0.85}
            >
              {isTaking ? (
                <ActivityIndicator size="large" color="#ffffff" />
              ) : (
                <View style={styles.captureInner} />
              )}
            </TouchableOpacity>
          </View>
        </View>
      </CameraView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    backgroundColor: '#000',
  },
  camera: {
    flex: 1,
  },
  overlayContainer: {
    flex: 1,
    justifyContent: 'space-between',
  },
  headerBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 20,
  },
  headerButton: {
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
  },
  headerButtonText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 14,
  },
  buttonContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: 40,
    alignItems: 'center',
  },
  captureButton: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'rgba(255, 255, 255, 0.3)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  captureInner: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#ffffff',
  },
  text: {
    color: 'white',
    textAlign: 'center',
    marginBottom: 20,
    fontSize: 16,
  },
  button: {
    backgroundColor: '#4f46e5',
    padding: 15,
    borderRadius: 12,
    marginHorizontal: 50,
    marginBottom: 12,
  },
  backButton: {
    backgroundColor: '#374151',
  },
  buttonText: {
    color: 'white',
    textAlign: 'center',
    fontWeight: 'bold',
  }
});
