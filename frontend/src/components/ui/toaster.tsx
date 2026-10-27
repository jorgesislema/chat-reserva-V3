'use client'

import { useToast } from '@/hooks/use-toast'
import { ToastProvider, Toast, ToastClose, ToastTitle, ToastDescription } from '@/components/ui/toast'

export function Toaster() {
  const { toasts } = useToast()

  return (
    <ToastProvider>
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-[380px] max-w-[calc(100vw-1rem)]">
        {toasts.map(({ id, title, description, variant, duration }) => (
          <Toast key={id} variant={variant} duration={duration}>
            <div className="grid gap-1">
              {title && <ToastTitle>{title}</ToastTitle>}
              {description && <ToastDescription>{description}</ToastDescription>}
            </div>
            <ToastClose />
          </Toast>
        ))}
      </div>
    </ToastProvider>
  )
}
