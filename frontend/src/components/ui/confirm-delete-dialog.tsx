import { useState, useCallback } from 'react'
import { AlertTriangle } from 'lucide-react'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

interface ConfirmDeleteDialogProps {
    readonly open: boolean
    readonly onConfirm: () => void
    readonly onCancel: () => void
    readonly title?: string
    readonly description?: string
    readonly loading?: boolean
}

export function ConfirmDeleteDialog({
    open,
    onConfirm,
    onCancel,
    title = '确认删除',
    description = '此操作不可撤销，相关数据将一并删除。',
    loading = false,
}: ConfirmDeleteDialogProps) {
    return (
        <Dialog open={open} onOpenChange={(v) => { if (!v) onCancel() }}>
            <DialogContent className="max-w-sm">
                <DialogHeader>
                    <div className="flex items-center gap-3">
                        <div className="flex items-center justify-center w-10 h-10 rounded-full bg-red-500/10 shrink-0">
                            <AlertTriangle className="size-5 text-red-500" />
                        </div>
                        <div>
                            <DialogTitle className="text-base">{title}</DialogTitle>
                            <DialogDescription className="mt-1">{description}</DialogDescription>
                        </div>
                    </div>
                </DialogHeader>
                <DialogFooter className="mt-2">
                    <Button variant="outline" size="sm" onClick={onCancel} disabled={loading}>
                        取消
                    </Button>
                    <Button variant="destructive" size="sm" onClick={onConfirm} disabled={loading}>
                        {loading ? '删除中…' : '确认删除'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

/**
 * Hook to manage confirm-delete dialog state.
 * Returns [dialogProps, openDialog] — spread dialogProps onto ConfirmDeleteDialog,
 * call openDialog(callback) to show the dialog.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useConfirmDelete() {
    const [open, setOpen] = useState(false)
    const [pending, setPending] = useState(false)
    const [callback, setCallback] = useState<(() => void) | null>(null)

    const openDialog = useCallback((onConfirm: () => void) => {
        setCallback(() => onConfirm)
        setOpen(true)
    }, [])

    const handleConfirm = useCallback(() => {
        setPending(true)
        callback?.()
        setOpen(false)
        setPending(false)
    }, [callback])

    const handleCancel = useCallback(() => {
        setOpen(false)
        setCallback(null)
    }, [])

    return [
        { open, onConfirm: handleConfirm, onCancel: handleCancel, loading: pending },
        openDialog,
    ] as const
}
