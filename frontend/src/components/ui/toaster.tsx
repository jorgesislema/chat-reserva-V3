'use client'

import { useToast } from '@/hooks/use-toast'
import { Toast, ToastClose, ToastTitle, ToastDescription, ToastAction } from '@/components/ui/toast'

export function Toaster() {
  const { toasts } = useToast()

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-[380px] max-w-[calc(100vw-1rem)]">
      {toasts.map(({ id, title, description, action, variant, duration }) => (
        <Toast key={id} variant={toast.variant} duration={duration}>
          <div className="grid gap-1">
            <ToastTitle>{title}</ToastTitle>
            <ToastDescription>{description}</ToastDescription>
          </div>
          <ToastClose />
        </Toast>
      ))}
    </div>
  )
}