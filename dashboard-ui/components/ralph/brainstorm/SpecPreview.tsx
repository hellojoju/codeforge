interface SpecPreviewProps {
  markdown: string
}

export default function SpecPreview({ markdown }: SpecPreviewProps) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <h3 className="text-sm font-semibold text-slate-700 mb-3">Spec Document</h3>
      <pre className="text-xs text-slate-600 whitespace-pre-wrap font-mono max-h-[400px] overflow-y-auto p-3 bg-slate-50 rounded">
        {markdown}
      </pre>
    </div>
  )
}
