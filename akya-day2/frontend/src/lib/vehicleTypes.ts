// Detector classes that have an icon (Stage 1 model: car, van, truck, bus).
export const hasTypeIcon = (type: string | null | undefined): boolean =>
  type === 'car' || type === 'van' || type === 'truck' || type === 'bus'
