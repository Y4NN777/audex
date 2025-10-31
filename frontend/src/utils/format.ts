export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 o";
  }
  const units = ["o", "Ko", "Mo", "Go", "To"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, exponent);
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[exponent]}`;
}
