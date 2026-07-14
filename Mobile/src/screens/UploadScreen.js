import React, { useState } from 'react';
import { 
  StyleSheet, Text, View, Image, TextInput, 
  TouchableOpacity, SafeAreaView, Switch, 
  KeyboardAvoidingView, Platform, ScrollView, ActivityIndicator,
  Alert
} from 'react-native';
import { previewPhoto, confirmUpload } from '../services/api';

export default function UploadScreen({ photoUri, onRetake, onUploadSuccess, prefilledArticleCode, nextImageIndex, fromPendingList }) {
  const [articleCode, setArticleCode] = useState(prefilledArticleCode || '');
  const [includeStamp, setIncludeStamp] = useState(false);
  const [imageIndex, setImageIndex] = useState(nextImageIndex || 0);
  const watermarkOpacity = 0.05; // Fixed at 5%
  const [errorMsg, setErrorMsg] = useState('');

  // Estados del flujo de 2 pasos
  const [screenState, setScreenState] = useState('form'); // 'form' | 'processing' | 'preview' | 'confirming'
  const [previewId, setPreviewId] = useState(null);
  const [previewImageUrl, setPreviewImageUrl] = useState(null);
  const [showOriginal, setShowOriginal] = useState(false); // Para comparar original vs procesada

  const handlePreview = async () => {
    if (!articleCode.trim()) {
      setErrorMsg('Debes ingresar un nombre o código para el artículo.');
      return;
    }

    setScreenState('processing');
    setErrorMsg('');

    try {
      const result = await previewPhoto(photoUri, articleCode, includeStamp, watermarkOpacity);
      setPreviewId(result.preview_id);
      setPreviewImageUrl(result.preview_image_url);
      setScreenState('preview');
    } catch (error) {
      setErrorMsg(error.message);
      setScreenState('form');
    }
  };

  const handleConfirmUpload = async () => {
    if (!previewId) return;

    setScreenState('confirming');
    setErrorMsg('');

    try {
      const result = await confirmUpload(previewId, articleCode, imageIndex);

      if (imageIndex < 3) {
        Alert.alert(
          'Foto subida',
          `Se subió la foto del producto "${articleCode}". ¿Deseas seguir sacando fotos adicionales del mismo producto?`,
          [
            {
              text: 'No',
              onPress: () => onUploadSuccess(articleCode, false, 0),
              style: 'cancel',
            },
            {
              text: 'Sí',
              onPress: () => onUploadSuccess(articleCode, true, imageIndex + 1),
            },
          ],
          { cancelable: false }
        );
      } else {
        Alert.alert('Éxito', result.message || 'Foto subida con éxito.', [
          {
            text: 'OK',
            onPress: () => onUploadSuccess(articleCode, false, 0)
          }
        ]);
      }
    } catch (error) {
      setErrorMsg(error.message);
      setScreenState('preview');
    }
  };

  const handleReprocess = () => {
    setPreviewId(null);
    setPreviewImageUrl(null);
    setShowOriginal(false);
    setScreenState('form');
  };

  // ==========================================
  // Estado: Procesando con IA
  // ==========================================
  if (screenState === 'processing') {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.processingContainer}>
          <View style={styles.processingCard}>
            <ActivityIndicator size="large" color="#4F8EF7" style={{ marginBottom: 20 }} />
            <Text style={styles.processingTitle}>Procesando con IA...</Text>
            <Text style={styles.processingSubtitle}>
              Removiendo fondo, aplicando marca de agua y ajustes digitales.
            </Text>
            <Text style={styles.processingHint}>
              Esto puede tardar unos segundos.
            </Text>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  // ==========================================
  // Estado: Preview (mostrando resultado de IA)
  // ==========================================
  if (screenState === 'preview' || screenState === 'confirming') {
    return (
      <SafeAreaView style={styles.container}>
        <ScrollView contentContainerStyle={styles.scrollContent}>

          <View style={styles.header}>
            <Text style={styles.headerText}>📸 Vista Previa Procesada</Text>
            <Text style={styles.headerSubtext}>
              Así quedará tu foto publicada. Revisá antes de confirmar.
            </Text>
          </View>

          {/* Imagen procesada (o original para comparar) */}
          <View style={styles.previewContainer}>
            <Image 
              source={{ uri: showOriginal ? photoUri : previewImageUrl }} 
              style={styles.previewImage} 
              resizeMode="contain" 
            />
            {/* Badge de estado */}
            <View style={[styles.imageBadge, showOriginal ? styles.badgeOriginal : styles.badgeProcessed]}>
              <Text style={styles.badgeText}>
                {showOriginal ? '📷 ORIGINAL' : '✨ PROCESADA'}
              </Text>
            </View>
          </View>

          {/* Botón comparar */}
          <TouchableOpacity
            style={styles.compareButton}
            onPressIn={() => setShowOriginal(true)}
            onPressOut={() => setShowOriginal(false)}
          >
            <Text style={styles.compareButtonText}>
              👆 Mantené presionado para ver la foto original
            </Text>
          </TouchableOpacity>

          {/* Info del artículo */}
          <View style={styles.previewInfoCard}>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Artículo:</Text>
              <Text style={styles.infoValue}>{articleCode}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Tipo:</Text>
              <Text style={styles.infoValue}>
                {imageIndex === 0 ? 'Principal' : `Adicional ${imageIndex}`}
              </Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Sello:</Text>
              <Text style={styles.infoValue}>{includeStamp ? 'Sí' : 'No'}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Marca de agua:</Text>
              <Text style={styles.infoValue}>{Math.round(watermarkOpacity * 100)}%</Text>
            </View>
          </View>

          {errorMsg ? <Text style={styles.errorText}>{errorMsg}</Text> : null}

          {/* Botones de acción */}
          <View style={styles.previewActions}>
            <TouchableOpacity
              style={[styles.actionButton, styles.confirmButton]}
              onPress={handleConfirmUpload}
              disabled={screenState === 'confirming'}
            >
              {screenState === 'confirming' ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <>
                  <Text style={styles.actionButtonIcon}>✅</Text>
                  <Text style={styles.actionButtonText}>Confirmar y Subir</Text>
                </>
              )}
            </TouchableOpacity>

            <View style={styles.secondaryActions}>
              <TouchableOpacity
                style={[styles.actionButton, styles.reprocessButton]}
                onPress={handleReprocess}
                disabled={screenState === 'confirming'}
              >
                <Text style={styles.actionButtonIcon}>🔄</Text>
                <Text style={[styles.actionButtonText, styles.secondaryButtonText]}>
                  Ajustar y reprocesar
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.actionButton, styles.retakeActionButton]}
                onPress={onRetake}
                disabled={screenState === 'confirming'}
              >
                <Text style={styles.actionButtonIcon}>📷</Text>
                <Text style={[styles.actionButtonText, styles.secondaryButtonText]}>
                  Retomar foto
                </Text>
              </TouchableOpacity>
            </View>
          </View>

        </ScrollView>
      </SafeAreaView>
    );
  }

  // ==========================================
  // Estado: Formulario (estado inicial)
  // ==========================================
  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.container}
      >
        <ScrollView contentContainerStyle={styles.scrollContent}>
          
          <View style={styles.header}>
            <Text style={styles.headerText}>Revisar y Procesar</Text>
          </View>

          <View style={styles.previewContainer}>
            <Image source={{ uri: photoUri }} style={styles.previewImage} resizeMode="contain" />
          </View>

          <View style={styles.formContainer}>
            <Text style={styles.label}>Nombre base / Código de Artículo:</Text>
            <TextInput
              style={styles.input}
              placeholder="Ej: R123 o Zapatillas-Nike"
              placeholderTextColor="#7a7a7a"
              value={articleCode}
              onChangeText={setArticleCode}
              autoCapitalize="none"
            />

            {/* Image type selector: hidden when coming from pending list */}
            {!fromPendingList && (
              <>
                <Text style={styles.label}>Tipo de Imagen:</Text>
                <View style={styles.typeContainer}>
                  {[0, 1, 2, 3].map((index) => (
                    <TouchableOpacity
                      key={index}
                      style={[
                        styles.typeButton,
                        imageIndex === index && styles.typeButtonSelected
                      ]}
                      onPress={() => setImageIndex(index)}
                    >
                      <Text style={[
                        styles.typeButtonText,
                        imageIndex === index && styles.typeButtonTextSelected
                      ]}>
                        {index === 0 ? 'Principal' : `Adic ${index}`}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </>
            )}

            <View style={styles.switchContainer}>
              <Text style={styles.switchLabel}>Incluir Sello (Oferta/Destacado)</Text>
              <Switch
                trackColor={{ false: "#3B4054", true: "#4F8EF7" }}
                thumbColor={includeStamp ? "#ffffff" : "#f4f3f4"}
                onValueChange={setIncludeStamp}
                value={includeStamp}
              />
            </View>

            {errorMsg ? <Text style={styles.errorText}>{errorMsg}</Text> : null}

            <View style={styles.buttonsContainer}>
              <TouchableOpacity 
                style={[styles.button, styles.retakeButton]} 
                onPress={onRetake}
              >
                <Text style={styles.buttonText}>Volver a tomar</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={[styles.button, styles.uploadButton]} 
                onPress={handlePreview}
              >
                <Text style={styles.buttonText}>🤖 Procesar con IA</Text>
              </TouchableOpacity>
            </View>
          </View>
          
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1E1F26',
  },
  scrollContent: {
    flexGrow: 1,
  },
  header: {
    padding: 20,
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#3B4054',
  },
  headerText: {
    color: '#ECEFF4',
    fontSize: 20,
    fontWeight: 'bold',
  },
  headerSubtext: {
    color: '#A7B0C0',
    fontSize: 13,
    marginTop: 4,
    textAlign: 'center',
  },
  previewContainer: {
    width: '100%',
    height: 350,
    backgroundColor: '#000',
    position: 'relative',
  },
  previewImage: {
    width: '100%',
    height: '100%',
  },
  imageBadge: {
    position: 'absolute',
    top: 12,
    right: 12,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
  },
  badgeProcessed: {
    backgroundColor: 'rgba(76, 175, 80, 0.9)',
  },
  badgeOriginal: {
    backgroundColor: 'rgba(255, 152, 0, 0.9)',
  },
  badgeText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: 'bold',
  },
  compareButton: {
    backgroundColor: '#252836',
    paddingVertical: 12,
    paddingHorizontal: 16,
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#3B4054',
    alignItems: 'center',
  },
  compareButtonText: {
    color: '#A7B0C0',
    fontSize: 13,
  },
  previewInfoCard: {
    backgroundColor: '#252836',
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 10,
    padding: 16,
    borderWidth: 1,
    borderColor: '#3B4054',
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
  },
  infoLabel: {
    color: '#A7B0C0',
    fontSize: 14,
  },
  infoValue: {
    color: '#ECEFF4',
    fontSize: 14,
    fontWeight: 'bold',
  },
  previewActions: {
    padding: 16,
    gap: 10,
  },
  actionButton: {
    borderRadius: 10,
    paddingVertical: 16,
    paddingHorizontal: 20,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  confirmButton: {
    backgroundColor: '#4CAF50',
  },
  reprocessButton: {
    backgroundColor: '#252836',
    borderWidth: 1,
    borderColor: '#4F8EF7',
    flex: 1,
    marginRight: 5,
  },
  retakeActionButton: {
    backgroundColor: '#252836',
    borderWidth: 1,
    borderColor: '#3B4054',
    flex: 1,
    marginLeft: 5,
  },
  secondaryActions: {
    flexDirection: 'row',
  },
  actionButtonIcon: {
    fontSize: 18,
  },
  actionButtonText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 16,
  },
  secondaryButtonText: {
    fontSize: 13,
    fontWeight: '600',
  },
  // Processing state
  processingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  processingCard: {
    backgroundColor: '#252836',
    borderRadius: 16,
    padding: 40,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#3B4054',
    width: '100%',
  },
  processingTitle: {
    color: '#ECEFF4',
    fontSize: 22,
    fontWeight: 'bold',
    marginBottom: 10,
  },
  processingSubtitle: {
    color: '#A7B0C0',
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 8,
  },
  processingHint: {
    color: '#4F8EF7',
    fontSize: 12,
    marginTop: 8,
  },
  // Form state
  formContainer: {
    padding: 20,
    flex: 1,
  },
  label: {
    color: '#A7B0C0',
    marginBottom: 8,
    fontWeight: '600',
  },
  input: {
    backgroundColor: '#252836',
    borderWidth: 1,
    borderColor: '#3B4054',
    borderRadius: 8,
    color: '#ECEFF4',
    padding: 15,
    fontSize: 16,
    marginBottom: 20,
  },
  typeContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  sliderHeaderContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  sliderValueText: {
    color: '#4F8EF7',
    fontSize: 16,
    fontWeight: 'bold',
  },
  typeButton: {
    flex: 1,
    backgroundColor: '#252836',
    borderWidth: 1,
    borderColor: '#3B4054',
    paddingVertical: 12,
    marginHorizontal: 3,
    borderRadius: 8,
    alignItems: 'center',
  },
  typeButtonSelected: {
    backgroundColor: '#4F8EF7',
    borderColor: '#4F8EF7',
  },
  typeButtonText: {
    color: '#A7B0C0',
    fontSize: 13,
    fontWeight: 'bold',
  },
  typeButtonTextSelected: {
    color: '#ffffff',
  },
  switchContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#252836',
    padding: 15,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#3B4054',
    marginBottom: 20,
  },
  switchLabel: {
    color: '#ECEFF4',
    fontSize: 16,
  },
  errorText: {
    color: '#E53935',
    marginBottom: 15,
    textAlign: 'center',
    fontWeight: 'bold',
  },
  buttonsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 'auto',
  },
  button: {
    flex: 1,
    padding: 15,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  retakeButton: {
    backgroundColor: '#3B4054',
    marginRight: 10,
  },
  uploadButton: {
    backgroundColor: '#4F8EF7',
    marginLeft: 10,
  },
  buttonText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 16,
  },
});
