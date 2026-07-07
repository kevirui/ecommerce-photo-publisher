import React from 'react';
import { StyleSheet, Text, View, TouchableOpacity, SafeAreaView, StatusBar } from 'react-native';

export default function WelcomeScreen({ onStartCamera, onViewPending }) {
  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />
      <View style={styles.content}>
        <View style={styles.logoContainer}>
          <View style={styles.logoIcon}>
            <Text style={styles.logoIconText}>📸</Text>
          </View>
          <Text style={styles.title}>Cimer Fotos</Text>
          <Text style={styles.subtitle}>Captura y sube tus fotos de forma rápida y sencilla</Text>
        </View>

        <View style={styles.infoCard}>
          <Text style={styles.infoText}>
            Usa esta aplicación para documentar el estado, tomar fotos de control o registrar evidencias.
          </Text>
        </View>

        <View style={styles.buttonContainer}>
          <TouchableOpacity style={styles.button} onPress={onStartCamera} activeOpacity={0.85}>
            <Text style={styles.buttonText}>Iniciar Cámara</Text>
          </TouchableOpacity>

          <TouchableOpacity style={[styles.button, styles.pendingButton]} onPress={onViewPending} activeOpacity={0.85}>
            <Text style={styles.buttonText}>Ver Pendientes de Foto</Text>
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#13141a',
  },
  content: {
    flex: 1,
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 30,
    paddingVertical: 60,
  },
  logoContainer: {
    alignItems: 'center',
    marginTop: 60,
  },
  logoIcon: {
    width: 90,
    height: 90,
    borderRadius: 45,
    backgroundColor: '#232533',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
    shadowColor: '#4f46e5',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 10,
    elevation: 8,
  },
  logoIconText: {
    fontSize: 42,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#ffffff',
    marginBottom: 12,
    letterSpacing: 0.5,
  },
  subtitle: {
    fontSize: 16,
    color: '#94a3b8',
    textAlign: 'center',
    paddingHorizontal: 20,
    lineHeight: 24,
  },
  infoCard: {
    backgroundColor: '#1e2030',
    padding: 20,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#2e3047',
    width: '100%',
    marginVertical: 40,
  },
  infoText: {
    color: '#cbd5e1',
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 22,
  },
  button: {
    backgroundColor: '#4f46e5',
    width: '100%',
    paddingVertical: 18,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#4f46e5',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 6,
  },
  buttonContainer: {
    width: '100%',
    gap: 15,
  },
  pendingButton: {
    backgroundColor: '#1e2030',
    borderWidth: 1,
    borderColor: '#2e3047',
    shadowColor: '#000000',
    shadowOpacity: 0.1,
  },
  buttonText: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: 'bold',
    letterSpacing: 0.5,
  },
});
