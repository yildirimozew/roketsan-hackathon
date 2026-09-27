import { Bus, Car, type LucideProps, Truck, Van } from 'lucide-react'

/** Icon for a detected vehicle type; renders nothing for an unknown type. Works in HTML and SVG. */
export function VehicleTypeIcon({
  vehicleType,
  ...props
}: LucideProps & { vehicleType: string | null | undefined }) {
  switch (vehicleType) {
    case 'car':
      return <Car aria-label={vehicleType} {...props} />
    case 'van':
      return <Van aria-label={vehicleType} {...props} />
    case 'truck':
      return <Truck aria-label={vehicleType} {...props} />
    case 'bus':
      return <Bus aria-label={vehicleType} {...props} />
    default:
      return null
  }
}
