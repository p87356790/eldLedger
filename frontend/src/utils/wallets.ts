import type { InstrumentKind, WalletAccount } from "../api/client";

export const KIND_ORDER: InstrumentKind[] = ["CASH", "BANK", "CREDIT_CARD", "LOAN", "OTHER_ASSET"];

export const KIND_LABEL: Record<InstrumentKind, string> = {
  CASH: "현금",
  BANK: "은행계좌",
  CREDIT_CARD: "신용카드",
  LOAN: "대출금",
  OTHER_ASSET: "기타자산",
};

export const INSTITUTIONS: Record<InstrumentKind, string[]> = {
  CASH: ["지갑", "금고", "기타"],
  BANK: [
    "국민은행",
    "신한은행",
    "우리은행",
    "하나은행",
    "농협은행",
    "기업은행",
    "카카오뱅크",
    "토스뱅크",
    "케이뱅크",
    "우체국",
    "기타",
  ],
  CREDIT_CARD: [
    "국민카드",
    "신한카드",
    "삼성카드",
    "현대카드",
    "우리카드",
    "롯데카드",
    "하나카드",
    "NH농협카드",
    "카카오뱅크",
    "기타",
  ],
  LOAN: ["주택담보대출", "신용대출", "마이너스통장", "기타"],
  OTHER_ASSET: ["비품", "예치금", "기타"],
};

export function groupWallets(wallets: WalletAccount[]): Record<InstrumentKind, WalletAccount[]> {
  const grouped: Record<InstrumentKind, WalletAccount[]> = {
    CASH: [],
    BANK: [],
    CREDIT_CARD: [],
    LOAN: [],
    OTHER_ASSET: [],
  };
  for (const wallet of wallets) {
    grouped[wallet.instrument_kind].push(wallet);
  }
  return grouped;
}

export function defaultWalletName(kind: InstrumentKind, institution: string, alias: string): string {
  const trimmedAlias = alias.trim();
  if (trimmedAlias !== "") {
    return trimmedAlias;
  }
  if (institution !== "" && institution !== "기타") {
    return institution;
  }
  return KIND_LABEL[kind];
}
