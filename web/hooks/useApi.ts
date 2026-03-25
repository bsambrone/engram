import useSWR from 'swr';
import { api } from '@/lib/api';

export function useApi<T>(path: string | null) {
  return useSWR<T>(path, (url: string) => api.get<T>(url));
}
