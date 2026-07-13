import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet, Text, View, Image, TouchableOpacity,
  SafeAreaView, ActivityIndicator, PanResponder, Dimensions
} from 'react-native';
import * as ImageManipulator from 'expo-image-manipulator';
import Slider from '@react-native-community/slider';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

export default function CropScreen({ photoUri, onCropDone, onCancel }) {
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [containerLayout, setContainerLayout] = useState({ width: 0, height: 0 });
  const [normalizedUri, setNormalizedUri] = useState(null);

  // Crop box state in pixels relative to the display container
  const [cropBox, setCropBox] = useState({ x: 50, y: 50, width: 200, height: 200 });

  // Ref to hold current state to prevent stale closures in PanResponder
  const stateRef = useRef({
    cropBox: { x: 50, y: 50, width: 200, height: 200 },
    imageSize: { width: 0, height: 0 },
    containerLayout: { width: 0, height: 0 }
  });

  // Keep ref synchronized with states
  useEffect(() => {
    stateRef.current.cropBox = cropBox;
  }, [cropBox]);

  useEffect(() => {
    stateRef.current.imageSize = imageSize;
  }, [imageSize]);

  useEffect(() => {
    stateRef.current.containerLayout = containerLayout;
  }, [containerLayout]);

  // Get image original dimensions after normalizing orientation
  useEffect(() => {
    if (photoUri) {
      setLoading(true);
      
      const prepareImage = async () => {
        try {
          // Normalize EXIF orientation by running a dummy manipulation.
          // This rotates and bakes orientation physically into the pixel layout.
          const normalized = await ImageManipulator.manipulateAsync(
            photoUri,
            [], 
            { compress: 0.9, format: ImageManipulator.SaveFormat.JPEG }
          );

          Image.getSize(
            normalized.uri,
            (width, height) => {
              setNormalizedUri(normalized.uri);
              setImageSize({ width, height });
              setLoading(false);
            },
            (error) => {
              console.error("Error getting size of normalized image:", error);
              fallbackToOriginal();
            }
          );
        } catch (err) {
          console.error("Error preparing image orientation normalization:", err);
          fallbackToOriginal();
        }
      };

      const fallbackToOriginal = () => {
        setNormalizedUri(photoUri);
        Image.getSize(
          photoUri,
          (width, height) => {
            setImageSize({ width, height });
            setLoading(false);
          },
          (error) => {
            console.error("Error getting original image size:", error);
            alert("No se pudo cargar la imagen para recortar.");
            onCancel();
          }
        );
      };

      prepareImage();
    }
  }, [photoUri]);

  // Adjust crop box when containerLayout changes or image size is loaded
  useEffect(() => {
    if (imageSize.width > 0 && containerLayout.width > 0) {
      const { displayedWidth, displayedHeight } = getDisplayedImageSize();
      const initialSize = Math.min(displayedWidth, displayedHeight) * 0.7;
      const x = (containerLayout.width - initialSize) / 2;
      const y = (containerLayout.height - initialSize) / 2;
      setCropBox({
        x: Math.max(0, x),
        y: Math.max(0, y),
        width: initialSize,
        height: initialSize
      });
    }
  }, [imageSize, containerLayout]);

  // Calculations for displayed image boundaries inside the container
  const getDisplayedImageSize = () => {
    const containerWidth = containerLayout.width || SCREEN_WIDTH;
    const containerHeight = containerLayout.height || (SCREEN_HEIGHT - 300);

    if (imageSize.width === 0 || imageSize.height === 0) {
      return { displayedWidth: containerWidth, displayedHeight: containerHeight, offsetLeft: 0, offsetTop: 0 };
    }

    const imageRatio = imageSize.width / imageSize.height;
    const containerRatio = containerWidth / containerHeight;

    let displayedWidth, displayedHeight;
    if (containerRatio > imageRatio) {
      // Height matches container, width is scaled down
      displayedHeight = containerHeight;
      displayedWidth = containerHeight * imageRatio;
    } else {
      // Width matches container, height is scaled down
      displayedWidth = containerWidth;
      displayedHeight = containerWidth / imageRatio;
    }

    const offsetLeft = (containerWidth - displayedWidth) / 2;
    const offsetTop = (containerHeight - displayedHeight) / 2;

    return { displayedWidth, displayedHeight, offsetLeft, offsetTop };
  };

  // Helper using latest ref values for PanResponder calculation
  const getDisplayedImageSizeFromRef = () => {
    const { imageSize: refImageSize, containerLayout: refContainerLayout } = stateRef.current;
    const containerWidth = refContainerLayout.width || SCREEN_WIDTH;
    const containerHeight = refContainerLayout.height || (SCREEN_HEIGHT - 300);

    if (refImageSize.width === 0 || refImageSize.height === 0) {
      return { displayedWidth: containerWidth, displayedHeight: containerHeight, offsetLeft: 0, offsetTop: 0 };
    }

    const imageRatio = refImageSize.width / refImageSize.height;
    const containerRatio = containerWidth / containerHeight;

    let displayedWidth, displayedHeight;
    if (containerRatio > imageRatio) {
      displayedHeight = containerHeight;
      displayedWidth = containerHeight * imageRatio;
    } else {
      displayedWidth = containerWidth;
      displayedHeight = containerWidth / imageRatio;
    }

    const offsetLeft = (containerWidth - displayedWidth) / 2;
    const offsetTop = (containerHeight - displayedHeight) / 2;

    return { displayedWidth, displayedHeight, offsetLeft, offsetTop };
  };

  // PanResponder start values
  const cropBoxStart = useRef({ x: 50, y: 50 });

  // PanResponder to make the crop box draggable
  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: () => {
        cropBoxStart.current = { x: stateRef.current.cropBox.x, y: stateRef.current.cropBox.y };
      },
      onPanResponderMove: (evt, gestureState) => {
        const { displayedWidth, displayedHeight, offsetLeft, offsetTop } = getDisplayedImageSizeFromRef();
        const currentCropBox = stateRef.current.cropBox;

        // Calculate new positions based on total distance from gesture start
        let newX = cropBoxStart.current.x + gestureState.dx;
        let newY = cropBoxStart.current.y + gestureState.dy;

        // Limit boundaries to the displayed image area
        const minX = offsetLeft;
        const maxX = offsetLeft + displayedWidth - currentCropBox.width;
        const minY = offsetTop;
        const maxY = offsetTop + displayedHeight - currentCropBox.height;

        newX = Math.max(minX, Math.min(maxX, newX));
        newY = Math.max(minY, Math.min(maxY, newY));

        setCropBox(prev => ({ ...prev, x: newX, y: newY }));
      }
    })
  ).current;

  const handleContainerLayout = (event) => {
    const { width, height } = event.nativeEvent.layout;
    setContainerLayout({ width, height });
  };

  const handleCrop = async () => {
    if (processing) return;
    setProcessing(true);

    try {
      const { displayedWidth, displayedHeight, offsetLeft, offsetTop } = getDisplayedImageSize();

      // Convert layout crop box to actual image pixels
      const scaleX = imageSize.width / displayedWidth;
      const scaleY = imageSize.height / displayedHeight;

      // Crop box relative to displayed image start coordinates
      const relativeX = cropBox.x - offsetLeft;
      const relativeY = cropBox.y - offsetTop;

      const originX = Math.max(0, Math.round(relativeX * scaleX));
      const originY = Math.max(0, Math.round(relativeY * scaleY));
      const width = Math.min(imageSize.width - originX, Math.round(cropBox.width * scaleX));
      const height = Math.min(imageSize.height - originY, Math.round(cropBox.height * scaleY));

      const manipResult = await ImageManipulator.manipulateAsync(
        normalizedUri,
        [{ crop: { originX, originY, width, height } }],
        { compress: 0.9, format: ImageManipulator.SaveFormat.JPEG }
      );

      onCropDone(manipResult.uri);
    } catch (error) {
      console.error("Error cropping image:", error);
      alert("No se pudo recortar la imagen.");
    } finally {
      setProcessing(false);
    }
  };

  const handleSliderChange = (key, value) => {
    setCropBox(prev => {
      const { displayedWidth, displayedHeight, offsetLeft, offsetTop } = getDisplayedImageSize();
      let updated = { ...prev, [key]: value };

      // Validate constraints
      if (key === 'width') {
        const maxWidth = offsetLeft + displayedWidth - prev.x;
        updated.width = Math.min(value, maxWidth);
      } else if (key === 'height') {
        const maxHeight = offsetTop + displayedHeight - prev.y;
        updated.height = Math.min(value, maxHeight);
      } else if (key === 'x') {
        const maxX = offsetLeft + displayedWidth - prev.width;
        updated.x = Math.max(offsetLeft, Math.min(maxX, value));
      } else if (key === 'y') {
        const maxY = offsetTop + displayedHeight - prev.height;
        updated.y = Math.max(offsetTop, Math.min(maxY, value));
      }

      return updated;
    });
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#4F8EF7" />
        <Text style={styles.loadingText}>Cargando imagen...</Text>
      </SafeAreaView>
    );
  }

  const { displayedWidth, displayedHeight, offsetLeft, offsetTop } = getDisplayedImageSize();

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>📐 Encuadrar Producto</Text>
        <Text style={styles.headerSubtitle}>Arrastra el recuadro o usa los controles para enfocar tu producto.</Text>
      </View>

      {/* Main Image Area with Crop Box Overlay */}
      <View 
        style={styles.imageContainer} 
        onLayout={handleContainerLayout}
      >
        <Image 
          source={{ uri: normalizedUri }} 
          style={styles.image} 
          resizeMode="contain"
        />

        {/* Shaded boundaries around the crop area */}
        <View style={[styles.shading, { left: 0, top: 0, width: cropBox.x, height: containerLayout.height }]} />
        <View style={[styles.shading, { left: cropBox.x + cropBox.width, top: 0, width: containerLayout.width - (cropBox.x + cropBox.width), height: containerLayout.height }]} />
        <View style={[styles.shading, { left: cropBox.x, top: 0, width: cropBox.width, height: cropBox.y }]} />
        <View style={[styles.shading, { left: cropBox.x, top: cropBox.y + cropBox.height, width: cropBox.width, height: containerLayout.height - (cropBox.y + cropBox.height) }]} />

        {/* Draggable Crop Box Overlay */}
        <View
          style={[
            styles.cropBox,
            {
              left: cropBox.x,
              top: cropBox.y,
              width: cropBox.width,
              height: cropBox.height,
            }
          ]}
          {...panResponder.panHandlers}
        >
          {/* Corner indicators for UI aesthetics */}
          <View style={[styles.corner, styles.topLeft]} />
          <View style={[styles.corner, styles.topRight]} />
          <View style={[styles.corner, styles.bottomLeft]} />
          <View style={[styles.corner, styles.bottomRight]} />
        </View>
      </View>

      {/* Control panel for fine-grained resizing */}
      <View style={styles.controlPanel}>
        <View style={styles.sliderRow}>
          <Text style={styles.sliderLabel}>Ancho:</Text>
          <Slider
            style={styles.slider}
            minimumValue={50}
            maximumValue={displayedWidth}
            value={cropBox.width}
            onValueChange={(val) => handleSliderChange('width', val)}
            minimumTrackTintColor="#4F8EF7"
            maximumTrackTintColor="#3B4054"
            thumbTintColor="#ffffff"
          />
        </View>

        <View style={styles.sliderRow}>
          <Text style={styles.sliderLabel}>Alto:</Text>
          <Slider
            style={styles.slider}
            minimumValue={50}
            maximumValue={displayedHeight}
            value={cropBox.height}
            onValueChange={(val) => handleSliderChange('height', val)}
            minimumTrackTintColor="#4F8EF7"
            maximumTrackTintColor="#3B4054"
            thumbTintColor="#ffffff"
          />
        </View>

        {/* Action buttons */}
        <View style={styles.buttonRow}>
          <TouchableOpacity 
            style={[styles.button, styles.cancelButton]} 
            onPress={onCancel}
            disabled={processing}
          >
            <Text style={styles.buttonText}>Omitir / Original</Text>
          </TouchableOpacity>

          <TouchableOpacity 
            style={[styles.button, styles.confirmButton]} 
            onPress={handleCrop}
            disabled={processing}
          >
            {processing ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Recortar e ir a subir</Text>
            )}
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
  loadingContainer: {
    flex: 1,
    backgroundColor: '#13141a',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#A7B0C0',
    marginTop: 10,
    fontSize: 16,
  },
  header: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#252836',
  },
  headerTitle: {
    color: '#ECEFF4',
    fontSize: 18,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  headerSubtitle: {
    color: '#A7B0C0',
    fontSize: 12,
    textAlign: 'center',
    marginTop: 4,
  },
  imageContainer: {
    flex: 1,
    position: 'relative',
    backgroundColor: '#000',
  },
  image: {
    width: '100%',
    height: '100%',
  },
  shading: {
    position: 'absolute',
    backgroundColor: 'rgba(0, 0, 0, 0.65)',
  },
  cropBox: {
    position: 'absolute',
    borderWidth: 2,
    borderColor: '#4F8EF7',
    backgroundColor: 'rgba(79, 142, 247, 0.05)',
  },
  corner: {
    position: 'absolute',
    width: 20,
    height: 20,
    borderColor: '#ffffff',
  },
  topLeft: {
    top: -2,
    left: -2,
    borderTopWidth: 4,
    borderLeftWidth: 4,
  },
  topRight: {
    top: -2,
    right: -2,
    borderTopWidth: 4,
    borderRightWidth: 4,
  },
  bottomLeft: {
    bottom: -2,
    left: -2,
    borderBottomWidth: 4,
    borderLeftWidth: 4,
  },
  bottomRight: {
    bottom: -2,
    right: -2,
    borderBottomWidth: 4,
    borderRightWidth: 4,
  },
  controlPanel: {
    backgroundColor: '#1E1F26',
    padding: 20,
    borderTopWidth: 1,
    borderTopColor: '#252836',
  },
  sliderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  sliderLabel: {
    color: '#A7B0C0',
    width: 60,
    fontSize: 14,
    fontWeight: 'bold',
  },
  slider: {
    flex: 1,
    height: 40,
  },
  buttonRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 10,
    gap: 12,
  },
  button: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelButton: {
    backgroundColor: '#3B4054',
  },
  confirmButton: {
    backgroundColor: '#4F8EF7',
  },
  buttonText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 14,
  },
});
