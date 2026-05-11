interface SpecPreviewProps {
  markdown: string
}

export default function SpecPreview({ markdown }: SpecPreviewProps) {
  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
      <h3 className="text-sm font-semibold text-slate-300 mb-3">Spec Document</h3>
      <pre className="text-xs text-slate-400 whitespace-pre-wrap font-mono max-h-[400px] overflow-y-auto p-3 bg-slate-900/50 rounded">
        {markdown}
      </pre>
    </div>
  )
}
