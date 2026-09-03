import type { SvgIconComponent } from "@mui/icons-material";
import CategoryIcon from "@mui/icons-material/Category";
import CommuteIcon from "@mui/icons-material/Commute";
import DirectionsCarIcon from "@mui/icons-material/DirectionsCar";
import FlightIcon from "@mui/icons-material/Flight";
import HomeIcon from "@mui/icons-material/Home";
import LaptopIcon from "@mui/icons-material/Laptop";
import LocalCafeIcon from "@mui/icons-material/LocalCafe";
import LocalGasStationIcon from "@mui/icons-material/LocalGasStation";
import MedicalServicesIcon from "@mui/icons-material/MedicalServices";
import PaymentsIcon from "@mui/icons-material/Payments";
import PetsIcon from "@mui/icons-material/Pets";
import PhoneIcon from "@mui/icons-material/Phone";
import ReceiptIcon from "@mui/icons-material/Receipt";
import RestaurantIcon from "@mui/icons-material/Restaurant";
import SavingsIcon from "@mui/icons-material/Savings";
import SchoolIcon from "@mui/icons-material/School";
import ShoppingBagIcon from "@mui/icons-material/ShoppingBag";
import SportsEsportsIcon from "@mui/icons-material/SportsEsports";
import StoreIcon from "@mui/icons-material/Store";
import WorkIcon from "@mui/icons-material/Work";

import type { Category, CategoryDefaultScope } from "../api/client";

export const SCOPE_LABEL: Record<CategoryDefaultScope, string> = {
  PERSONAL: "개인",
  BUSINESS: "사업",
  COMMON: "공통",
};

export const ICON_CHOICES: Array<{ id: string; label: string; Icon: SvgIconComponent }> = [
  { id: "category", label: "기본", Icon: CategoryIcon },
  { id: "home", label: "생활", Icon: HomeIcon },
  { id: "restaurant", label: "식사", Icon: RestaurantIcon },
  { id: "phone", label: "통신", Icon: PhoneIcon },
  { id: "commute", label: "교통", Icon: CommuteIcon },
  { id: "receipt", label: "사무", Icon: ReceiptIcon },
  { id: "work", label: "사업", Icon: WorkIcon },
  { id: "payments", label: "수입", Icon: PaymentsIcon },
  { id: "local_cafe", label: "접대", Icon: LocalCafeIcon },
  { id: "directions_car", label: "차량", Icon: DirectionsCarIcon },
  { id: "shopping_bag", label: "쇼핑", Icon: ShoppingBagIcon },
  { id: "flight", label: "출장", Icon: FlightIcon },
  { id: "store", label: "거래처", Icon: StoreIcon },
  { id: "laptop", label: "온라인", Icon: LaptopIcon },
  { id: "local_gas_station", label: "주유", Icon: LocalGasStationIcon },
  { id: "medical_services", label: "의료", Icon: MedicalServicesIcon },
  { id: "school", label: "교육", Icon: SchoolIcon },
  { id: "pets", label: "반려동물", Icon: PetsIcon },
  { id: "sports_esports", label: "여가", Icon: SportsEsportsIcon },
  { id: "savings", label: "저축", Icon: SavingsIcon },
];

const ICON_MAP: Record<string, SvgIconComponent> = Object.fromEntries(
  ICON_CHOICES.map((item) => [item.id, item.Icon]),
);

export function categoryIcon(name: string | null): SvgIconComponent {
  if (name !== null && name in ICON_MAP) {
    return ICON_MAP[name];
  }
  return CategoryIcon;
}

export interface CategoryNode {
  category: Category;
  children: Category[];
}

export function buildCategoryForest(categories: Category[]): CategoryNode[] {
  const byParent = new Map<number | null, Category[]>();
  for (const category of categories) {
    const key = category.parent_id;
    const siblings = byParent.get(key) ?? [];
    siblings.push(category);
    byParent.set(key, siblings);
  }
  const roots = (byParent.get(null) ?? []).slice().sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name, "ko"));
  return roots.map((category) => ({
    category,
    children: (byParent.get(category.id) ?? [])
      .slice()
      .sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name, "ko")),
  }));
}

export function flattenCategoryTree(categories: Category[]): Category[] {
  const rows: Category[] = [];
  for (const node of buildCategoryForest(categories)) {
    rows.push(node.category);
    rows.push(...node.children);
  }
  return rows;
}

export function categoryLabel(category: Category, all: Category[]): string {
  if (category.parent_id === null) {
    return category.name;
  }
  const parent = all.find((item) => item.id === category.parent_id);
  return parent === undefined ? category.name : `${parent.name} / ${category.name}`;
}
