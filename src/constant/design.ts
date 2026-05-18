import {
  ArchitectIcon,
  BathroomIcon,
  BedroomIcon,
  DecoratorIcon,
  KitchenIcon,
  LightIcon,
  LivingRoomIcon,
  OfficeIcon,
  RugIcon,
  SofaIcon,
  StorageIcon,
  TableChairIcon,
  TreeIcon,
} from "@/components/icons";

export const SEARCH_QUICK_TAGS = ["giường", "tủ", "đèn"];

export const CATEGORY_ICONS: Record<string, React.ComponentType> = {
  "Phòng khách": LivingRoomIcon,
  "Phòng ngủ": BedroomIcon,
  "Nhà bếp": KitchenIcon,
  "Nhà tắm": BathroomIcon,
  "Văn phòng": OfficeIcon,
  "Kiến trúc": ArchitectIcon,
  "Trang trí": DecoratorIcon,
  "Chiếu sáng": LightIcon,
  "Cây cảnh": TreeIcon,
  "Lưu trữ": StorageIcon,
  "Bàn ghế": TableChairIcon,
  Sofa: SofaIcon,
  Thảm: RugIcon,
};
