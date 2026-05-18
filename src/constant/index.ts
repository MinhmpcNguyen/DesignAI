import { TPresets } from "@/types/global";

export const DefaultPrompts = [
  "Ánh sáng không quá sáng, màu sắc tự nhiên, ảnh nội thất chân thực",
  "Nội thất chân thực, ánh sáng tự nhiên, màu sắc thật, bề mặt có độ nhám nhẹ",
  "Chi tiết rõ nét, phản chiếu tự nhiên, ảnh giống chụp bằng máy ảnh",
  "Nội thất siêu chân thực, gỗ vải kính kim loại trông giống ngoài đời, chi tiết rõ nét, màu sắc tự nhiên, ảnh chụp nội thất bằng máy ảnh, cảm giác như ảnh thật",
  "Chọn góc chụp rộng nhìn hơn và đẹp hơn, phù hợp với không gian nội thất",
  "Đặt cửa số ở vị trí phù hợp để tạo ra ánh sáng tự nhiên tốt nhất",
  "Sàn gỗ óc chó tối màu, Sofa vải lanh màu kem, Kệ TV gỗ sồi sáng màu, Tường thạch cao, Rèm vải voai trắng",
];

export const PresetLightings: TPresets[] = [
  {
    key: "daylight_1",
    label: "Hừng đông",
    imgUrl: "/presets/lightnings/daylight_1.png",
  },
  {
    key: "daylight_2",
    label: "Chính ngọ",
    imgUrl: "/presets/lightnings/daylight_2.png",
  },
  {
    key: "daylight_3",
    label: "Hoàng hôn",
    imgUrl: "/presets/lightnings/daylight_3.png",
  },
  {
    key: "night_1",
    label: "Tự nhiên",
    imgUrl: "/presets/lightnings/night_1.png",
  },
  {
    key: "night_2",
    label: "Chạng vạng",
    imgUrl: "/presets/lightnings/night_2.png",
  },
];

export const PresetStyles: TPresets[] = [
  { key: "modern", label: "Hiện đại", imgUrl: "/presets/styles/modern.png" },
  {
    key: "neo_classic",
    label: "Tân cổ điển",
    imgUrl: "/presets/styles/neo-classic.png",
  },
  {
    key: "wabi_sabi",
    label: "Wabi-Sabi",
    imgUrl: "/presets/styles/wabi-sabi.png",
  },
];

export const PresetSceneries: TPresets[] = [
  { key: "city", label: "Thành phố", imgUrl: "/presets/sceneries/city.png" },
  {
    key: "coastal",
    label: "Ven biển",
    imgUrl: "/presets/sceneries/coastal.png",
  },
  {
    key: "countryside",
    label: "Nông thôn",
    imgUrl: "/presets/sceneries/countryside.png",
  },
  {
    key: "mountain",
    label: "Vùng núi",
    imgUrl: "/presets/sceneries/mountain.png",
  },
];

/** Default material id — referenced by the floor Redux slice initial state */
export const DEFAULT_FLOOR_MATERIAL_ID = "classic";

/** Drag data type for dropping shapes into the scene */
export const SHAPE_DRAG_TYPE = "application/x-room-design-shape";
