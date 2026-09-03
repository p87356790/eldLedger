function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

export function isoDate(year: number, month: number, day: number): string {
  return `${year}-${pad2(month)}-${pad2(day)}`;
}

export function splitIsoDate(iso: string): { year: number; month: number; day: number } {
  const [yearText, monthText, dayText] = iso.split("-");
  return {
    year: Number.parseInt(yearText ?? "0", 10),
    month: Number.parseInt(monthText ?? "0", 10),
    day: Number.parseInt(dayText ?? "0", 10),
  };
}

export function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

export function monthStartIso(year: number, month: number): string {
  return isoDate(year, month, 1);
}

export function monthEndIso(year: number, month: number): string {
  return isoDate(year, month, daysInMonth(year, month));
}

export function currentMonthRange(): { start: string; end: string; year: number; month: number } {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  return { start: monthStartIso(year, month), end: monthEndIso(year, month), year, month };
}

export function shiftYearMonth(year: number, month: number, delta: number): { year: number; month: number } {
  const shifted = new Date(year, month - 1 + delta, 1);
  return { year: shifted.getFullYear(), month: shifted.getMonth() + 1 };
}

export function weekdaySundayZero(year: number, month: number, day: number): number {
  return new Date(year, month - 1, day).getDay();
}

export function formatYearMonthKo(year: number, month: number): string {
  return `${year}년 ${month}월`;
}

export function formatDayHeading(iso: string): string {
  const { year, month, day } = splitIsoDate(iso);
  const weekday = ["일", "월", "화", "수", "목", "금", "토"][weekdaySundayZero(year, month, day)] ?? "";
  return `${year}년 ${month}월 ${day}일 (${weekday})`;
}

export function buildMonthCells(year: number, month: number): Array<number | null> {
  const leading = weekdaySundayZero(year, month, 1);
  const total = daysInMonth(year, month);
  const cells: Array<number | null> = [];
  for (let index = 0; index < leading; index += 1) {
    cells.push(null);
  }
  for (let day = 1; day <= total; day += 1) {
    cells.push(day);
  }
  while (cells.length % 7 !== 0) {
    cells.push(null);
  }
  return cells;
}
