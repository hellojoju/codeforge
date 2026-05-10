interface GranularityBadgeProps {
  missingItems: string[]
}

export default function GranularityBadge({ missingItems }: GranularityBadgeProps) {
  if (missingItems.length === 0) {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-emerald-500/20 text-emerald-400">粒度通过</span>
  }
  return (
    <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-amber-500/20 text-amber-400">
      <span>缺失 {missingItems.length} 项</span>
    </div>
  )
}
