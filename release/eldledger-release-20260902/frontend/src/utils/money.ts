export function parseWon(value: string): number {
  const digits = value.replace(/[^\d]/g, "");
  if (digits === "") {
    return 0;
  }
  return Number.parseInt(digits, 10);
}

export function formatWon(amount: number): string {
  return amount.toLocaleString("ko-KR");
}

export function formatWonWithSymbol(amount: number): string {
  return `₩${formatWon(amount)}`;
}

export function todayIsoDate(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

export function formatDisplayDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-");
  if (year === undefined || month === undefined || day === undefined) {
    return isoDate;
  }
  return `${Number.parseInt(month, 10)}월 ${Number.parseInt(day, 10)}일`;
}
