// Lets any LLM text on the watch page open a vehicle by its id without prop drilling.
import { createContext, useContext } from 'react'

export const VehicleLinkContext = createContext<(trackId: string) => void>(() => undefined)

export const useVehicleLink = () => useContext(VehicleLinkContext)
