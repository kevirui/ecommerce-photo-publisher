import React, { useState } from 'react';
import { 
  StyleSheet, Text, View, Image, TextInput, 
  TouchableOpacity, SafeAreaView, Switch, 
  KeyboardAvoidingView, Platform, ScrollView, ActivityIndicator
} from 'react-native';
import Slider from '@react-native-community/slider';
import { uploadPhoto } from '../services/api';

export default function UploadScreen({ photoUri, onRetake, onUploadSuccess, prefilledArticleCode }) {
  const [articleCode, setArticleCode] = useState(prefilledArticleCode || '');
  const [includeStamp, setIncludeStamp] = useState(false);
  const [imageIndex, setImageIndex] = useState(0);
  const [watermarkOpacity, setWatermarkOpacity] = useState(0.3); // Default 30%
  const [isUploading, setIsUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleUpload = async () => {
    if (!articleCode.trim()) {
      setErrorMsg('Debes ingresar un nombre o código para el artículo.');
      return;
    }

    setIsUploading(true);
    setErrorMsg('');

    try {
      const result = await uploadPhoto(photoUri, articleCode, includeStamp, imageIndex, watermarkOpacity);
      alert('Éxito: ' + result.message);
      onUploadSuccess();
    } catch (error) {
      setErrorMsg(error.message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.container}
      >
        <ScrollView contentContainerStyle={styles.scrollContent}>
          
          <View style={styles.header}>
            <Text style={styles.headerText}>Revisar y Subir</Text>
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
              editable={!isUploading}
            />

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
                  disabled={isUploading}
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

            <View style={styles.sliderHeaderContainer}>
              <Text style={[styles.label, { marginBottom: 0 }]}>Transparencia de Marca de Agua:</Text>
              <Text style={styles.sliderValueText}>{`${Math.round(watermarkOpacity * 100)}%`}</Text>
            </View>
            <Slider
              style={styles.slider}
              minimumValue={0}
              maximumValue={1}
              step={0.01}
              value={watermarkOpacity}
              onValueChange={(val) => setWatermarkOpacity(parseFloat(val.toFixed(2)))}
              minimumTrackTintColor="#4F8EF7"
              maximumTrackTintColor="#3B4054"
              thumbTintColor="#ffffff"
              disabled={isUploading}
            />

            <View style={styles.switchContainer}>
              <Text style={styles.switchLabel}>Incluir Sello (Oferta/Destacado)</Text>
              <Switch
                trackColor={{ false: "#3B4054", true: "#4F8EF7" }}
                thumbColor={includeStamp ? "#ffffff" : "#f4f3f4"}
                onValueChange={setIncludeStamp}
                value={includeStamp}
                disabled={isUploading}
              />
            </View>

            {errorMsg ? <Text style={styles.errorText}>{errorMsg}</Text> : null}

            <View style={styles.buttonsContainer}>
              <TouchableOpacity 
                style={[styles.button, styles.retakeButton]} 
                onPress={onRetake}
                disabled={isUploading}
              >
                <Text style={styles.buttonText}>Volver a tomar</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={[styles.button, styles.uploadButton]} 
                onPress={handleUpload}
                disabled={isUploading}
              >
                {isUploading ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.buttonText}>Procesar y Subir</Text>
                )}
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
  previewContainer: {
    width: '100%',
    height: 350,
    backgroundColor: '#000',
  },
  previewImage: {
    width: '100%',
    height: '100%',
  },
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
  slider: {
    width: '100%',
    height: 40,
    marginBottom: 20,
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
  }
});
