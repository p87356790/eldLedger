import { Card, CardContent, List, ListItem, ListItemText, Typography } from "@mui/material";

const REPORTS: Array<{ title: string; hint: string }> = [
  { title: "거래원장", hint: "날짜별로 들어온 돈과 나간 돈을 모아 봅니다." },
  { title: "계정별 원장", hint: "계좌·분류별로 흐름을 봅니다." },
  { title: "분개장", hint: "고급: 거래가 어떻게 장부에 올라갔는지 봅니다." },
  { title: "시산표", hint: "고급: 계정 잔액이 맞는지 확인합니다." },
  { title: "사업자 보고서", hint: "회사로 기록한 거래만 모아 세무사에게 넘길 자료를 만듭니다." },
];

export function ReportsPage() {
  return (
    <Card>
      <CardContent sx={{ p: { xs: 2.5, sm: 3.5 } }}>
        <Typography variant="h5" sx={{ fontWeight: 800 }}>
          보고서
        </Typography>
        <Typography color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
          시산표·분개장 같은 회계 보고서는 이 메뉴에서만 씁니다. 화면 내용은 이어서 붙일 예정이에요.
        </Typography>
        <List disablePadding>
          {REPORTS.map((item) => (
            <ListItem key={item.title} sx={{ px: 0 }}>
              <ListItemText primary={item.title} secondary={item.hint} />
            </ListItem>
          ))}
        </List>
      </CardContent>
    </Card>
  );
}
