import { CheckCircle2, Clock, Files } from "lucide-react";

type Stat = {
  label: string;
  value: string;
  caption?: string;
  icon: React.ReactNode;
};

type Props = {
  stats: Stat[];
};

export function StatsStrip({ stats }: Props) {
  return (
    <section className="stats-strip">
      {stats.map((stat) => (
        <article key={stat.label} className="stats-card">
          <div className="stats-icon">{stat.icon}</div>
          <div className="stats-copy">
            <p className="stats-value">{stat.value}</p>
            <p className="stats-label">{stat.label}</p>
            {stat.caption && <p className="stats-caption">{stat.caption}</p>}
          </div>
        </article>
      ))}
    </section>
  );
}

export function buildStats({
  totalBatches,
  pending,
  totalFiles,
  totalSize
}: {
  totalBatches: number;
  pending: number;
  totalFiles: number;
  totalSize: string;
}): Stat[] {
  return [
    {
      label: "Lots au total",
      value: totalBatches.toString(),
      caption: `${pending} en attente`,
      icon: <Files size={24} strokeWidth={1.8} />
    },
    {
      label: "Fichiers enregistrés",
      value: totalFiles.toString(),
      icon: <CheckCircle2 size={24} strokeWidth={1.8} />
    },
    {
      label: "Volume stocké",
      value: totalSize,
      icon: <Clock size={24} strokeWidth={1.8} />
    }
  ];
}
