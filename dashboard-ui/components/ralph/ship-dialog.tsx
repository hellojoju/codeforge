import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface ShipDialogProps {
  workId: string
  onClose: () => void
  onShipped: () => void
}

export function ShipDialog({ workId, onClose, onShipped }: ShipDialogProps) {
  const [version, setVersion] = useState('')
  const [notes, setNotes] = useState('')

  const handleShip = () => {
    onShipped()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <Card className="w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <CardHeader>
          <CardTitle>Ship Work Unit</CardTitle>
          <p className="text-sm text-muted-foreground">
            Finalize and ship work unit {workId}
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium">Version</label>
            <Input
              placeholder="e.g. 1.0.0"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium">Release Notes</label>
            <Input
              placeholder="Optional release notes..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={handleShip}>Ship</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
