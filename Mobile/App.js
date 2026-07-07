import { StatusBar } from 'expo-status-bar';
import { StyleSheet, View } from 'react-native';
import { useState } from 'react';
import WelcomeScreen from './src/screens/WelcomeScreen';
import CameraScreen from './src/screens/CameraScreen';
import UploadScreen from './src/screens/UploadScreen';
import PendingScreen from './src/screens/PendingScreen';

export default function App() {
  const [screen, setScreen] = useState('welcome');
  const [photoUri, setPhotoUri] = useState(null);
  const [prefilledArticleCode, setPrefilledArticleCode] = useState('');
  const [lastUploadedCode, setLastUploadedCode] = useState('');
  const [pendingVisited, setPendingVisited] = useState(false);

  const handleStartCamera = () => {
    setPrefilledArticleCode('');
    setScreen('camera');
  };

  const handlePhotoTaken = (uri) => {
    setPhotoUri(uri);
    setScreen('upload');
  };

  const handleRetake = () => {
    setPhotoUri(null);
    setScreen('camera');
  };

  const handleUploadSuccess = () => {
    setPhotoUri(null);
    if (prefilledArticleCode) {
      setLastUploadedCode(prefilledArticleCode);
      setScreen('pending');
    } else {
      setScreen('welcome');
    }
    setPrefilledArticleCode('');
  };

  const handleGoBackToWelcome = () => {
    setPendingVisited(false);
    setScreen('welcome');
  };

  const handleSelectProduct = (code) => {
    setPrefilledArticleCode(code);
    setScreen('camera');
  };

  const handleViewPending = () => {
    setPendingVisited(true);
    setScreen('pending');
  };

  // Keep PendingScreen mounted while in camera/upload flow from pending
  const fromPending = prefilledArticleCode !== '' || screen === 'pending';
  const keepPendingAlive = pendingVisited && (screen === 'pending' || fromPending);

  return (
    <View style={styles.container}>
      <StatusBar style="light" />
      {screen === 'welcome' && (
        <WelcomeScreen 
          onStartCamera={handleStartCamera} 
          onViewPending={handleViewPending}
        />
      )}
      {keepPendingAlive && (
        <View style={[styles.fullScreen, screen !== 'pending' && styles.hidden]}>
          <PendingScreen 
            onBack={handleGoBackToWelcome}
            onSelectProduct={handleSelectProduct}
            lastUploadedCode={lastUploadedCode}
            onClearLastUploaded={() => setLastUploadedCode('')}
          />
        </View>
      )}
      {screen === 'camera' && (
        <CameraScreen 
          onPhotoTaken={handlePhotoTaken} 
          onBack={prefilledArticleCode ? () => setScreen('pending') : handleGoBackToWelcome}
        />
      )}
      {screen === 'upload' && photoUri && (
        <UploadScreen 
          photoUri={photoUri} 
          onRetake={handleRetake} 
          onUploadSuccess={handleUploadSuccess} 
          prefilledArticleCode={prefilledArticleCode}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#13141a',
  },
  fullScreen: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 1,
  },
  hidden: {
    display: 'none',
  },
});
