// UI-facing aliases of generated API types. Never hand-write API shapes; add aliases here.
import type { components, paths } from './schema'

type Schemas = components['schemas']

export type Analysis = Schemas['Analysis']
export type Brief = Schemas['Brief']
export type ComponentStatus = Schemas['ComponentStatus']
export type Detection = Schemas['Detection']
export type Health = Schemas['Health']
export type ImageMeta = Schemas['ImageMeta']
export type LatLon = Schemas['LatLon']
export type MapReport = Schemas['MapReport']
export type MapTrack = Schemas['MapTrack']
export type MotionProfile = Schemas['MotionProfile']
export type ReportAssessment = Schemas['ReportAssessment']
export type ReportCheck = Schemas['ReportCheck']
export type ReportClaim = Schemas['ReportClaim']
export type RiskFactor = Schemas['RiskFactor']
export type Scene = Schemas['Scene']
export type StepResult = Schemas['StepResult']
export type Stop = Schemas['Stop']
export type TrackMatch = Schemas['TrackMatch']
export type TrackPoint = Schemas['TrackPoint']
export type TrackSnapshot = Schemas['TrackSnapshot']
export type VehicleBriefLine = Schemas['VehicleBriefLine']
export type VehicleRisk = Schemas['VehicleRisk']

export type RiskLevel = Brief['level']
export type Verdict = ReportAssessment['verdict']
export type StepName = StepResult['step']
export type StepStatus = StepResult['status']
export type RecommendedAction = Brief['recommended_action']
export type CheckName = ReportCheck['name']

// Watch mode (recorded demo runs)
export type WatchRecording = Schemas['WatchRecording']
export type WatchEvent =
  paths['/api/watch/recordings/{recording_id}']['get']['responses'][200]['content']['application/json'][number]
export type WatchEventOf<K extends WatchEvent['type']> = Extract<WatchEvent, { type: K }>
export type VehicleRow = Schemas['VehicleRow']
export type WatchLevel = VehicleRow['registry_level']
export type OperatorAlert = Schemas['OperatorAlert']
export type FrameDetection = Schemas['FrameDetection']
export type FieldReport = Schemas['FieldReport']
export type ExpectedVehicle = Schemas['ExpectedVehicle']
export type ReportJudgment = Schemas['ReportJudgment']
export type ReportVerdict = ReportJudgment['verdict']

// Admin tuning
export type AgentTuning = Schemas['AgentTuning']
export type TuningView = Schemas['TuningView']
export type PromptPreview = Schemas['PromptPreview']
export type PromptName = Schemas['PromptPreviewRequest']['name']
export type Tier = Schemas['Tier']
