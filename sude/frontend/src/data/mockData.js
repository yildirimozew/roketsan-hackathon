export const vehicles = [
  {
    id: "V001",
    type: "Truck",
    confidence: 0.94,

    location: [39.9334, 32.8597],

    route: [
      [39.9298, 32.8535],
      [39.9309, 32.8551],
      [39.9321, 32.8568],
      [39.9334, 32.8597],
    ],

    movementHistory: [
    {
    time: "14:05",
    type: "detected",
    text: "Araç ilk kez tespit edildi",
    },
    {
    time: "14:32",
    type: "direction",
    text: "Kuzeydoğu yönüne hareket ediyor",
    },
    {
    time: "15:04",
    type: "speed",
    text: "Hız artışı tespit edildi",
    },
    {
    time: "15:38",
    type: "warning",
    text: "İzlenen bölgeye yaklaşıyor",
    },
    {
    time: "15:52",
    type: "report",
    text: "Saha raporu ile eşleşme bulundu",
    },
    ],

    bbox: {
      x: 27,
      y: 34,
      width: 17,
      height: 20,
    },

    risk: {
      level: "HIGH",
      confidence: 0.87,
      reasoning:
        "Araç üs yönünde ilerliyor ve son hareket kayıtlarında hız artışı gözlemlendi.",

      factors: [
        "Üs bölgesine yaklaşıyor",
        "Hız artışı tespit edildi",
        "Saha raporuyla tutarlı",
      ],
    },
  },

  {
    id: "V002",
    type: "Car",
    confidence: 0.88,

    location: [39.9278, 32.8665],

    route: [
      [39.9315, 32.8610],
      [39.9304, 32.8628],
      [39.9291, 32.8645],
      [39.9278, 32.8665],
    ],

    movementHistory: [
    {
    time: "14:12",
    type: "detected",
    text: "Araç ilk kez tespit edildi",
    },
    {
    time: "14:46",
    type: "direction",
    text: "Güneydoğu yönünde hareket ediyor",
    },
    {
    time: "15:15",
    type: "speed",
    text: "Hız değişimi normal",
    },
    {
    time: "15:41",
    type: "safe",
    text: "İzlenen bölgeden uzaklaşıyor",
    },
    ],

    bbox: {
      x: 66,
      y: 57,
      width: 13,
      height: 15,
    },

    risk: {
      level: "LOW",
      confidence: 0.76,
      reasoning:
        "Araç üs bölgesinden uzaklaşan bir rota izliyor ve olağandışı hareket tespit edilmedi.",

      factors: [
        "Üsten uzaklaşıyor",
        "Hız değişimi normal",
        "Şüpheli hareket tespit edilmedi",
      ],
    },
  },
];

export const fieldReports = [
  {
    id: "RPT-012",
    time: "15:47",
    region: "Bölge 01",
    text: "Ağır vasıta tipi bir aracın izlenen bölge yönünde ilerlediği bildirildi.",
    vehicleId: "V001",
    status: "supported",
  },
  {
    id: "RPT-018",
    time: "15:21",
    region: "Bölge 01",
    text: "Binek aracın olağandışı şekilde hızlandığı bildirildi.",
    vehicleId: "V002",
    status: "contradicted",
  },
  {
    id: "RPT-021",
    time: "15:55",
    region: "Bölge 01",
    text: "Bölgede kimliği belirlenemeyen başka bir araç görüldüğü bildirildi.",
    vehicleId: null,
    status: "unverified",
  },
];