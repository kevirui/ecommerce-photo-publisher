import * as FileSystem from 'expo-file-system';

const FILE_PATH = `${FileSystem.documentDirectory}photo_count.json`;

const getTodayString = () => {
  return new Date().toISOString().split('T')[0];
};

export const getDailyProductCodes = async () => {
  try {
    const today = getTodayString();
    const fileInfo = await FileSystem.getInfoAsync(FILE_PATH);
    if (fileInfo.exists) {
      const content = await FileSystem.readAsStringAsync(FILE_PATH);
      const data = JSON.parse(content);
      if (data.date === today) {
        return data.codes || [];
      }
    }
  } catch (error) {
    console.error('Error reading daily product codes:', error);
  }
  return [];
};

export const registerProductUploaded = async (articleCode) => {
  if (!articleCode) return 0;
  const cleanCode = articleCode.trim().toUpperCase();
  try {
    const today = getTodayString();
    let codes = [];
    
    const fileInfo = await FileSystem.getInfoAsync(FILE_PATH);
    if (fileInfo.exists) {
      try {
        const content = await FileSystem.readAsStringAsync(FILE_PATH);
        const data = JSON.parse(content);
        if (data.date === today) {
          codes = data.codes || [];
        }
      } catch (_) {}
    }
    
    if (!codes.includes(cleanCode)) {
      codes.push(cleanCode);
      await FileSystem.writeAsStringAsync(FILE_PATH, JSON.stringify({ date: today, codes }));
    }
    
    return codes.length;
  } catch (error) {
    console.error('Error registering product upload:', error);
    return 0;
  }
};
