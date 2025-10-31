import { Activity, AlertTriangle, CheckCircle2, Files, GaugeCircle } from "lucide-react";

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
  totalSize,
  completed,
  averageRisk,
  criticalObservations
}: {
  totalBatches: number;
  pending: number;
  totalFiles: number;
  totalSize: string;
  completed: number;
  averageRisk: number | null;
  criticalObservations: number;
}): Stat[] {
  const stats: Stat[] = [
    {
      label: "Lots au total",
      value: totalBatches.toString(),
      caption: `${pending} en attente`,
      icon: <Files size={24} strokeWidth={1.8} />
    },
    {
      label: "Lots complétés",
      value: completed.toString(),
      caption: completed === totalBatches ? "Synchronisation à jour" : "Analyses en cours",
      icon: <CheckCircle2 size={24} strokeWidth={1.8} />
    },
    {
      label: "Fichiers enregistrés",
      value: totalFiles.toString(),
      icon: <Activity size={24} strokeWidth={1.8} />
    },
    {
      label: "Volume stocké",
      value: totalSize,
      icon: <GaugeCircle size={24} strokeWidth={1.8} />
    }
  ];

  stats.push({
    label: "Score moyen",
    value: averageRisk !== null ? `${Math.round(averageRisk * 100)}%` : "N/A",
    caption: averageRisk !== null ? "Score normalisé" : "En attente de données",
    icon: <GaugeCircle size={24} strokeWidth={1.8} />
  });

  stats.push({
    label: "Observations critiques",
    value: criticalObservations.toString(),
    caption: "Sévérité « high »",
    icon: <AlertTriangle size={24} strokeWidth={1.8} />
  });

  return stats;
}
