/** 选中对象：四类详情（业务 / Flow / 链路 / 节点）共用同一个抽屉。 */
export type Selection =
  | { kind: "service"; id: string }
  | { kind: "flow"; id: string }
  | { kind: "link"; id: string }
  | { kind: "node"; id: string }
  | null;
