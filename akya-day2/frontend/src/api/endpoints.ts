import type { components } from './schema'
import { API_BASE_URL, USE_MOCKS, apiDelete, apiGet, apiPost, apiPut } from './client'
import type {
  AgentTuning,
  Analysis,
  Health,
  ImageMeta,
  MapReport,
  MapTrack,
  MotionProfile,
  PromptName,
  PromptPreview,
  Scene,
  TuningView,
  WatchEvent,
  WatchRecording,
} from './types'

type AnalysisCreated = components['schemas']['AnalysisCreated']

export const getHealth = () => apiGet<Health>('/api/health')
export const getScene = () => apiGet<Scene>('/api/scene')
export const getImages = () => apiGet<ImageMeta[]>('/api/images')
export const getTracks = () => apiGet<MapTrack[]>('/api/tracks')
export const getReports = () => apiGet<MapReport[]>('/api/reports')
export const getTrackMotion = (trackId: string, at: string) =>
  apiGet<MotionProfile>(
    `/api/tracks/${encodeURIComponent(trackId)}/motion?at=${encodeURIComponent(at)}`,
  )
export const getAnalysis = (analysisId: string) =>
  apiGet<Analysis>(`/api/analyses/${encodeURIComponent(analysisId)}`)
export const createAnalysis = (imageId: string, forceRefresh = false) =>
  apiPost<AnalysisCreated>('/api/analyses', { image_id: imageId, force_refresh: forceRefresh })

export const getRecordings = () => apiGet<WatchRecording[]>('/api/watch/recordings')
export const getRecording = (recordingId: string) =>
  apiGet<WatchEvent[]>(`/api/watch/recordings/${encodeURIComponent(recordingId)}`)

export const imageUrl = (imageId: string): string =>
  USE_MOCKS
    ? `/mock-images/${encodeURIComponent(imageId)}.jpg`
    : `${API_BASE_URL}/api/images/${encodeURIComponent(imageId)}/file`

export const getTuning = () => apiGet<TuningView>('/api/admin/tuning')
export const putTuning = (tuning: AgentTuning) => apiPut<TuningView>('/api/admin/tuning', tuning)
export const deleteTuning = () => apiDelete<TuningView>('/api/admin/tuning')
export const previewPrompt = (name: PromptName, text: string, tuning: AgentTuning) =>
  apiPost<PromptPreview>('/api/admin/prompts/preview', { name, text, tuning })
