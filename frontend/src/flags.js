// FIFA 三字码 → 旗帜 emoji（英格兰/苏格兰使用 Unicode 标签序列旗）
export const FLAGS = {
  MEX: '🇲🇽', RSA: '🇿🇦', KOR: '🇰🇷', CZE: '🇨🇿',
  SUI: '🇨🇭', CAN: '🇨🇦', BIH: '🇧🇦', QAT: '🇶🇦',
  BRA: '🇧🇷', MAR: '🇲🇦', SCO: '🏴󠁧󠁢󠁳󠁣󠁴󠁿', HAI: '🇭🇹',
  USA: '🇺🇸', AUS: '🇦🇺', PAR: '🇵🇾', TUR: '🇹🇷',
  GER: '🇩🇪', CIV: '🇨🇮', ECU: '🇪🇨', CUW: '🇨🇼',
  NED: '🇳🇱', JPN: '🇯🇵', SWE: '🇸🇪', TUN: '🇹🇳',
  BEL: '🇧🇪', EGY: '🇪🇬', IRN: '🇮🇷', NZL: '🇳🇿',
  ESP: '🇪🇸', CPV: '🇨🇻', URU: '🇺🇾', KSA: '🇸🇦',
  FRA: '🇫🇷', NOR: '🇳🇴', SEN: '🇸🇳', IRQ: '🇮🇶',
  ARG: '🇦🇷', AUT: '🇦🇹', ALG: '🇩🇿', JOR: '🇯🇴',
  COL: '🇨🇴', POR: '🇵🇹', COD: '🇨🇩', UZB: '🇺🇿',
  ENG: '🏴󠁧󠁢󠁥󠁮󠁧󠁿', CRO: '🇭🇷', GHA: '🇬🇭', PAN: '🇵🇦',
}

export function flag(code) {
  return FLAGS[code] || '🏳️'
}
