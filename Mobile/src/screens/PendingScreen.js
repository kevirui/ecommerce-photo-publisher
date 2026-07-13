import React, { useState, useEffect } from 'react';
import { 
  StyleSheet, Text, View, FlatList, TextInput, 
  TouchableOpacity, SafeAreaView, ActivityIndicator, StatusBar, ScrollView 
} from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { getPendingProducts, getPendingProductsFromExcel, markProductHasPhoto, markProductNoStock } from '../services/api';

export default function PendingScreen({ onBack, onSelectProduct, lastUploadedCode, onClearLastUploaded }) {
  const [products, setProducts] = useState([]);
  const [filteredProducts, setFilteredProducts] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('TODOS');
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');

  const [isExcelActive, setIsExcelActive] = useState(false);
  const [excelFileName, setExcelFileName] = useState('');

  useEffect(() => {
    fetchProducts();
  }, []);

  useEffect(() => {
    if (lastUploadedCode) {
      setProducts(prev => {
        const updated = prev.filter(p => p.codigo !== lastUploadedCode);
        applyFilters(updated, searchQuery, selectedCategory);
        return updated;
      });
      onClearLastUploaded();
    }
  }, [lastUploadedCode]);

  const fetchProducts = async () => {
    setIsLoading(true);
    setErrorMsg('');
    try {
      const data = await getPendingProducts();
      setProducts(data);
      setFilteredProducts(data);
      setSelectedCategory('TODOS');
      setSearchQuery('');
    } catch (error) {
      setErrorMsg(error.message || 'Error al cargar productos pendientes.');
    } finally {
      setIsLoading(false);
    }
  };

  const getCategories = () => {
    const cats = new Set(products.map(p => (p.categoria || 'OTROS').trim()));
    const filteredCats = Array.from(cats).filter(c => {
      const upper = c.toUpperCase();
      return upper !== 'TODOS' && upper !== '.TODOS' && upper !== '';
    });
    return ['TODOS', ...filteredCats.sort()];
  };

  const applyFilters = (rawProducts, queryText, cat) => {
    let filtered = rawProducts;
    
    if (cat && cat !== 'TODOS') {
      filtered = filtered.filter(item => (item.categoria || 'OTROS') === cat);
    }
    
    if (queryText.trim()) {
      const q = queryText.toUpperCase();
      filtered = filtered.filter(item => {
        const codeMatch = item.codigo && item.codigo.toUpperCase().includes(q);
        const descMatch = item.descripcion && item.descripcion.toUpperCase().includes(q);
        const catMatch = item.categoria && item.categoria.toUpperCase().includes(q);
        return codeMatch || descMatch || catMatch;
      });
    }
    
    setFilteredProducts(filtered);
  };

  const handleSearch = (text) => {
    setSearchQuery(text);
    applyFilters(products, text, selectedCategory);
  };

  const handleSelectCategory = (cat) => {
    setSelectedCategory(cat);
    applyFilters(products, searchQuery, cat);
  };

  const handleLoadExcel = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: [
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'application/vnd.ms-excel',
        ],
        copyToCacheDirectory: true,
      });

      if (result.canceled || !result.assets || result.assets.length === 0) {
        return;
      }

      const file = result.assets[0];
      setIsLoading(true);
      setErrorMsg('');
      
      try {
        const data = await getPendingProductsFromExcel(file.uri);
        setProducts(data);
        setExcelFileName(file.name);
        setIsExcelActive(true);
        setSelectedCategory('TODOS');
        setSearchQuery('');
        setFilteredProducts(data);
      } catch (error) {
        setErrorMsg(error.message || 'Error al procesar el archivo Excel.');
      } finally {
        setIsLoading(false);
      }
    } catch (err) {
      console.error(err);
      alert('Error al seleccionar el archivo.');
    }
  };

  const handleClearExcel = () => {
    setIsExcelActive(false);
    setExcelFileName('');
    setSelectedCategory('TODOS');
    setSearchQuery('');
    fetchProducts();
  };

  const handleMarkHasPhoto = async (code) => {
    try {
      setIsLoading(true);
      await markProductHasPhoto(code);
      setProducts(prev => {
        const updated = prev.filter(p => p.codigo !== code);
        applyFilters(updated, searchQuery, selectedCategory);
        return updated;
      });
    } catch (error) {
      alert(error.message || 'Error al marcar el artículo.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleMarkNoStock = async (code) => {
    try {
      setIsLoading(true);
      await markProductNoStock(code);
      setProducts(prev => {
        const updated = prev.filter(p => p.codigo !== code);
        applyFilters(updated, searchQuery, selectedCategory);
        return updated;
      });
    } catch (error) {
      alert(error.message || 'Error al marcar artículo sin stock.');
    } finally {
      setIsLoading(false);
    }
  };

  const renderProductItem = ({ item }) => {
    return (
      <View style={styles.card}>
        <View style={styles.cardContent}>
          <View style={styles.cardHeader}>
            <Text style={styles.productCode}>{item.codigo}</Text>
            <View style={styles.stockBadge}>
              <Text style={styles.stockText}>Stock: {item.stock}</Text>
            </View>
          </View>
          <Text style={styles.productDesc} numberOfLines={2}>
            {item.descripcion || 'Sin descripción'}
          </Text>
          <View style={styles.cardFooter}>
            <Text style={styles.productCategory}>🏷️ {item.categoria || 'OTROS'}</Text>
            <Text style={styles.productObs} numberOfLines={1}>
              {item.observaciones}
            </Text>
          </View>
        </View>
        <View style={styles.actionsColumn}>
          <TouchableOpacity 
            style={styles.cameraButton} 
            onPress={() => onSelectProduct(item.codigo)}
            activeOpacity={0.8}
          >
            <Text style={styles.cameraButtonIcon}>📸</Text>
            <Text style={styles.cameraButtonText}>Foto</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={styles.hasPhotoButton} 
            onPress={() => handleMarkHasPhoto(item.codigo)}
            activeOpacity={0.8}
          >
            <Text style={styles.hasPhotoButtonText}>✓ Ya tiene</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={styles.noStockButton} 
            onPress={() => handleMarkNoStock(item.codigo)}
            activeOpacity={0.8}
          >
            <Text style={styles.noStockButtonText}>⚠️ Sin Stock</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  const categories = getCategories();

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />
      
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={onBack} style={styles.backButton}>
          <Text style={styles.backButtonText}>✕ Volver</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Pendientes de Foto</Text>
        <TouchableOpacity 
          onPress={isExcelActive ? handleClearExcel : fetchProducts} 
          style={styles.refreshButton} 
          disabled={isLoading}
        >
          <Text style={styles.refreshButtonText}>🔄</Text>
        </TouchableOpacity>
      </View>

      {/* Control Excel */}
      <View style={styles.excelControlContainer}>
        {isExcelActive ? (
          <View style={styles.excelActiveRow}>
            <Text style={styles.excelActiveText} numberOfLines={1}>
              📄 {excelFileName}
            </Text>
            <TouchableOpacity onPress={handleClearExcel} style={styles.clearExcelButton}>
              <Text style={styles.clearExcelButtonText}>Quitar filtro</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <TouchableOpacity onPress={handleLoadExcel} style={styles.loadExcelButton} disabled={isLoading}>
            <Text style={styles.loadExcelButtonText}>📥 Cargar Excel de Pendientes</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Buscador */}
      <View style={styles.searchContainer}>
        <TextInput
          style={styles.searchInput}
          placeholder="Buscar por código, descripción o categoría..."
          placeholderTextColor="#7a7a7a"
          value={searchQuery}
          onChangeText={handleSearch}
          autoCapitalize="none"
          autoCorrect={false}
          clearButtonMode="while-editing"
        />
      </View>

      {/* Categorías (Pills) */}
      {!isLoading && !errorMsg && categories.length > 1 && (
        <View style={styles.categoriesContainer}>
          <ScrollView 
            horizontal 
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.categoriesScroll}
          >
            {categories.map(cat => (
              <TouchableOpacity
                key={cat}
                style={[
                  styles.categoryPill,
                  selectedCategory === cat && styles.categoryPillActive
                ]}
                onPress={() => handleSelectCategory(cat)}
              >
                <Text style={[
                  styles.categoryPillText,
                  selectedCategory === cat && styles.categoryPillTextActive
                ]}>
                  {cat}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      )}

      {/* Contenido Principal */}
      {isLoading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color="#4F8EF7" />
          <Text style={styles.loadingText}>Cargando productos pendientes...</Text>
        </View>
      ) : errorMsg ? (
        <View style={styles.centerContainer}>
          <Text style={styles.errorText}>{errorMsg}</Text>
          <TouchableOpacity style={styles.retryButton} onPress={isExcelActive ? handleClearExcel : fetchProducts}>
            <Text style={styles.retryButtonText}>Reintentar</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={filteredProducts}
          keyExtractor={(item) => item.codigo}
          renderItem={renderProductItem}
          contentContainerStyle={styles.listContent}
          initialNumToRender={15}
          maxToRenderPerBatch={15}
          windowSize={10}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>
                {searchQuery || selectedCategory !== 'TODOS'
                  ? 'No se encontraron artículos que coincidan con los filtros.' 
                  : 'No hay artículos pendientes de fotografiar en stock.'}
              </Text>
            </View>
          }
          ListHeaderComponent={
            <Text style={styles.resultsCount}>
              {filteredProducts.length} productos pendientes {isExcelActive ? 'filtrados por Excel' : ''} en stock
            </Text>
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#13141a',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#2e3047',
  },
  backButton: {
    paddingVertical: 6,
    paddingHorizontal: 10,
  },
  backButtonText: {
    color: '#94a3b8',
    fontSize: 15,
    fontWeight: 'bold',
  },
  headerTitle: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: 'bold',
  },
  refreshButton: {
    padding: 6,
  },
  refreshButtonText: {
    fontSize: 18,
  },
  excelControlContainer: {
    paddingHorizontal: 16,
    paddingTop: 12,
  },
  loadExcelButton: {
    backgroundColor: '#232533',
    borderWidth: 1,
    borderColor: '#3B4054',
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadExcelButtonText: {
    color: '#ECEFF4',
    fontSize: 13,
    fontWeight: 'bold',
  },
  excelActiveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'rgba(79, 142, 247, 0.1)',
    borderWidth: 1,
    borderColor: '#4F8EF7',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
  },
  excelActiveText: {
    color: '#ECEFF4',
    fontSize: 13,
    fontWeight: 'bold',
    flex: 1,
    marginRight: 10,
  },
  clearExcelButton: {
    backgroundColor: '#E53935',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  clearExcelButtonText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: 'bold',
  },
  searchContainer: {
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  searchInput: {
    backgroundColor: '#1e2030',
    borderWidth: 1,
    borderColor: '#2e3047',
    borderRadius: 12,
    color: '#ffffff',
    paddingHorizontal: 15,
    paddingVertical: 12,
    fontSize: 15,
  },
  categoriesContainer: {
    paddingVertical: 6,
  },
  categoriesScroll: {
    paddingHorizontal: 16,
    gap: 8,
  },
  categoryPill: {
    backgroundColor: '#1e2030',
    borderWidth: 1,
    borderColor: '#2e3047',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  categoryPillActive: {
    backgroundColor: '#4F8EF7',
    borderColor: '#4F8EF7',
  },
  categoryPillText: {
    color: '#94a3b8',
    fontSize: 13,
    fontWeight: 'bold',
  },
  categoryPillTextActive: {
    color: '#ffffff',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 30,
  },
  loadingText: {
    color: '#94a3b8',
    marginTop: 12,
    fontSize: 15,
  },
  errorText: {
    color: '#ef4444',
    textAlign: 'center',
    fontSize: 15,
    marginBottom: 20,
    fontWeight: 'bold',
  },
  retryButton: {
    backgroundColor: '#4f46e5',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
  },
  retryButtonText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 15,
  },
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 20,
  },
  resultsCount: {
    color: '#64748b',
    fontSize: 13,
    marginBottom: 10,
    fontWeight: '600',
  },
  card: {
    backgroundColor: '#1e2030',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#2e3047',
    padding: 16,
    marginBottom: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  cardContent: {
    flex: 1,
    marginRight: 12,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  productCode: {
    color: '#4F8EF7',
    fontSize: 16,
    fontWeight: 'bold',
    marginRight: 10,
  },
  stockBadge: {
    backgroundColor: 'rgba(79, 142, 247, 0.15)',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  stockText: {
    color: '#4F8EF7',
    fontSize: 11,
    fontWeight: 'bold',
  },
  productDesc: {
    color: '#ECEFF4',
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 6,
  },
  cardFooter: {
    flexDirection: 'column',
  },
  productCategory: {
    color: '#94a3b8',
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
  },
  productObs: {
    color: '#64748b',
    fontSize: 12,
  },
  cameraButton: {
    backgroundColor: '#4f46e5',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    width: 60,
    height: 60,
  },
  cameraButtonIcon: {
    fontSize: 20,
    marginBottom: 2,
  },
  cameraButtonText: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: 'bold',
  },
  actionsColumn: {
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  hasPhotoButton: {
    backgroundColor: '#10b981',
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    width: 60,
  },
  hasPhotoButtonText: {
    color: '#ffffff',
    fontSize: 9,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  noStockButton: {
    backgroundColor: '#ef4444',
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    width: 60,
  },
  noStockButtonText: {
    color: '#ffffff',
    fontSize: 9,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  emptyContainer: {
    paddingVertical: 40,
    alignItems: 'center',
  },
  emptyText: {
    color: '#64748b',
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 22,
  },
});
