import { StatusBar } from 'expo-status-bar';
import { StyleSheet, View, Platform, StatusBar as RNStatusBar } from 'react-native';
import { useState, useEffect } from 'react';
import WelcomeScreen from './src/screens/WelcomeScreen';
import CameraScreen from './src/screens/CameraScreen';
import UploadScreen from './src/screens/UploadScreen';
import PendingScreen from './src/screens/PendingScreen';

import { getDailyProductCodes, registerProductUploaded } from './src/services/photoCounter';

export default function App() {
  const [screen, setScreen] = useState('welcome');
  const [photoUri, setPhotoUri] = useState(null);
  const [fromPendingList, setFromPendingList] = useState(false);
  const [prefilledArticleCode, setPrefilledArticleCode] = useState('');
  const [lastUploadedCode, setLastUploadedCode] = useState('');
  const [pendingVisited, setPendingVisited] = useState(false);
  const [nextImageIndex, setNextImageIndex] = useState(0);
  const [photoQueue, setPhotoQueue] = useState([]);
  const [queueIndex, setQueueIndex] = useState(0);
  const [todayCount, setTodayCount] = useState(0);

  useEffect(() => {
    const loadDailyCount = async () => {
      const codes = await getDailyProductCodes();
      setTodayCount(codes.length);
    };
    loadDailyCount();
  }, []);

  const handleStartCamera = () => {
    setPrefilledArticleCode('');
    setNextImageIndex(0);
    setPhotoQueue([]);
    setQueueIndex(0);
    setFromPendingList(false);
    setScreen('camera');
  };

  const handlePhotoTaken = (uri) => {
    setPhotoQueue([uri]);
    setQueueIndex(0);
    setPhotoUri(uri);
    setScreen('upload');
  };

  const handlePhotosSelected = (uris) => {
    setPhotoQueue(uris);
    setQueueIndex(0);
    setPhotoUri(uris[0]);
    // The first one is imageIndex = 0 (Principal) or if prefilled index is different
    setNextImageIndex(0);
    setScreen('upload');
  };



  const handleRetake = () => {
    setPhotoUri(null);
    setPhotoQueue([]);
    setQueueIndex(0);
    setScreen('camera');
  };

  const handleUploadSuccess = (uploadedCode, keepTakingPhotos, nextIndex = 0) => {
    const activeCode = uploadedCode || prefilledArticleCode;
    if (activeCode) {
      registerProductUploaded(activeCode).then(newCount => {
        if (newCount > 0) setTodayCount(newCount);
      });
    }

    setPhotoUri(null);
    
    const nextQueueIndex = queueIndex + 1;
    if (keepTakingPhotos && nextQueueIndex < photoQueue.length) {
      // Advance in the gallery queue
      setQueueIndex(nextQueueIndex);
      const nextUri = photoQueue[nextQueueIndex];
      setPhotoUri(nextUri);
      setNextImageIndex(nextQueueIndex);
      setPrefilledArticleCode(uploadedCode);
      setScreen('upload');
    } else {
      // Normal flow or queue finished
      setPhotoQueue([]);
      setQueueIndex(0);
      
      if (keepTakingPhotos) {
        setNextImageIndex(nextIndex);
        setPrefilledArticleCode(uploadedCode);
        setScreen('camera');
      } else {
        setNextImageIndex(0);
        setLastUploadedCode(uploadedCode || prefilledArticleCode);
        setPendingVisited(true);
        setScreen('pending');
        setPrefilledArticleCode('');
      }
    }
  };

  const handleGoBackToWelcome = () => {
    setPendingVisited(false);
    setScreen('welcome');
  };

  const handleSelectProduct = (code) => {
    setPrefilledArticleCode(code);
    setNextImageIndex(0);
    setPhotoQueue([]);
    setQueueIndex(0);
    setFromPendingList(true);
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
          todayCount={todayCount}
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
          onPhotosSelected={handlePhotosSelected}
          onBack={prefilledArticleCode ? () => setScreen('pending') : handleGoBackToWelcome}
        />
      )}
      {screen === 'upload' && photoUri && (
        <UploadScreen 
          photoUri={photoUri} 
          onRetake={handleRetake} 
          onUploadSuccess={handleUploadSuccess} 
          prefilledArticleCode={prefilledArticleCode}
          nextImageIndex={nextImageIndex}
          fromPendingList={fromPendingList}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#13141a',
    paddingTop: Platform.OS === 'android' ? RNStatusBar.currentHeight : 0,
  },
  fullScreen: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 1,
  },
  hidden: {
    display: 'none',
  },
});
