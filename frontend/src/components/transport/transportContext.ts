import type { InjectionKey } from 'vue'
import type { TransportController } from './useTransport'

export const TRANSPORT_KEY: InjectionKey<TransportController> = Symbol('transport-controller')
