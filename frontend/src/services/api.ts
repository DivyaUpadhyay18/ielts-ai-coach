import axios from 'axios';

// We use the environment variable we defined earlier
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// This service handles the IELTS-specific requests
export const ieltsService = {
  // Check if API is running
  checkHealth: async () => {
    const response = await api.get('/health');
    return response.data;
  },

  // Send essay/text for assessment
  submitAssessment: async (data: {
    task_type: string;
    user_input: string;
    user_id: string;
  }) => {
    // Note: The backend expects band_score, feedback, etc. 
    // In a real flow, the AI would generate those, 
    // but for now, we define the structure.
    const response = await api.post('/assess', data);
    return response.data;
  },

  // Get past results
  getUserResults: async (userId: string) => {
    const response = await api.get(`/results/${userId}`);
    return response.data;
  }
};

export default api;