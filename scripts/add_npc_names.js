const fs = require('fs');
const path = require('path');
const npcs = JSON.parse(fs.readFileSync('./data/npcs.json'));

const newEntries = {
  alassa: {name:"Alassa", game:"bg2", recruitable:true},
  ariena: {name:"Ariena", game:"bg2", recruitable:true},
  askaria: {name:"Askaria", game:"bg2"},
  aura: {name:"Aura", game:"both", recruitable:true},
  barb_comp: {name:"Barbarian Companion", game:"bg2", recruitable:true},
  barbe: {name:"Barbe", game:"bg2", recruitable:true},
  brage: {name:"Brage", game:"bg1", recruitable:true},
  brandock: {name:"Brandock", game:"bg2", recruitable:true},
  calin: {name:"Calin", game:"bg2", recruitable:true},
  cassius: {name:"Cassius", game:"bg2", recruitable:true},
  chaos_knight: {name:"Chaos Knight", game:"bg2"},
  chiara: {name:"Chiara", game:"bg2", recruitable:true},
  chiara_wolf: {name:"Chiara (Wolf Form)", game:"bg2"},
  clara: {name:"Clara", game:"bg2", recruitable:true},
  clara_little: {name:"Little Clara", game:"bg2"},
  cliffhistory: {name:"Cliffette", game:"bg1"},
  cowled_shade: {name:"Cowled Shade", game:"tob"},
  darian: {name:"Darian", game:"bg2", recruitable:true},
  deepgnome_aurora: {name:"Aurora (Deepgnome)", game:"bg1", recruitable:true},
  dusk_npc: {name:"Dusk", game:"bg2", recruitable:true},
  dvaradime: {name:"Dvaradime", game:"bg2", recruitable:true},
  evandra: {name:"Evandra", game:"bg2", recruitable:true},
  faren: {name:"Faren", game:"bg2", recruitable:true},
  fhaugy: {name:"Fhaugy", game:"bg2", recruitable:true},
  fyalvara: {name:"Fyalvara", game:"bg2", recruitable:true},
  gahesh: {name:"Gahesh", game:"bg2", recruitable:true},
  gemma: {name:"Gemma", game:"bg2", recruitable:true},
  gorgon: {name:"Gorgon", game:"bg1", recruitable:true},
  grey_dog: {name:"Grey the Dog", game:"bg2", recruitable:true},
  helga: {name:"Helga", game:"bg2", recruitable:true},
  hendak: {name:"Hendak", game:"bg2", recruitable:true},
  horace: {name:"Horace", game:"bg2", recruitable:true},
  jenlig: {name:"Jenlig", game:"bg2", recruitable:true},
  jini: {name:"Jini", game:"bg2", recruitable:true},
  jini_doof: {name:"Doof", game:"bg2"},
  jini_pstr: {name:"Pstr", game:"bg2"},
  juniper: {name:"Juniper", game:"tob", recruitable:true},
  kale: {name:"Kale", game:"bg2", recruitable:true},
  kiara: {name:"Kiara", game:"bg2", recruitable:true},
  kido: {name:"Kido", game:"bg2", recruitable:true},
  kim: {name:"Kim", game:"bg2", recruitable:true},
  kitanya: {name:"Kitanya", game:"bg2", recruitable:true},
  kvel: {name:"Kvel", game:"bg1", recruitable:true},
  larsha: {name:"Larsha", game:"bg2", recruitable:true},
  lena: {name:"Lena", game:"bg2", recruitable:true},
  malthis: {name:"Malthis", game:"bg2", recruitable:true},
  mawgul: {name:"Mawgul", game:"bg2", recruitable:true},
  mhoram: {name:"Mhoram", game:"bg2", recruitable:true},
  moddie: {name:"Moddie", game:"bg2", recruitable:true},
  nathaniel: {name:"Nathaniel", game:"bg2", recruitable:true},
  navarra: {name:"Navarra", game:"bg2", recruitable:true},
  nehtaniel: {name:"Neh'taniel", game:"bg2", recruitable:true},
  nephele: {name:"Nephele", game:"bg2", recruitable:true},
  neris: {name:"Neris", game:"bg1", recruitable:true},
  nikita: {name:"Nikita", game:"bg2", recruitable:true},
  nina: {name:"Ninafer", game:"bg2", recruitable:true},
  ooze_nym: {name:"Nym", game:"bg2"},
  ophysia: {name:"Ophysia", game:"bg1", recruitable:true},
  orelios: {name:"Orelios", game:"bg2", recruitable:true},
  paina: {name:"Pai'Na", game:"bg2", recruitable:true},
  rjali: {name:"Rjali", game:"bg2", recruitable:true},
  rjali_doof: {name:"Doof (Rjali)", game:"bg2"},
  rjali_ini: {name:"Ini (Rjali)", game:"bg2"},
  rjali_mai: {name:"Mai (Rjali)", game:"bg2"},
  rjali_psta: {name:"Psta (Rjali)", game:"bg2"},
  rjali_pstg: {name:"Pstg (Rjali)", game:"bg2"},
  rose: {name:"Rose", game:"bg2", recruitable:true},
  sandra: {name:"Sandra", game:"bg2", recruitable:true},
  sandrah: {name:"Sandrah", game:"bg2", recruitable:true},
  saradas: {name:"Saradas", game:"tob", recruitable:true},
  sarah_npc: {name:"Sarah", game:"tob", recruitable:true},
  severian: {name:"Severian", game:"bg2", recruitable:true},
  silver_star: {name:"Silver Star", game:"bg2", recruitable:true},
  sister_bhaalspawn: {name:"Sister of Bhaalspawn", game:"bg2", recruitable:true},
  solaufein: {name:"Solaufein", game:"bg2", recruitable:true},
  tashia: {name:"Tashia", game:"bg2", recruitable:true},
  thael: {name:"Thael", game:"bg2", recruitable:true},
  thael_sindel: {name:"Sindel", game:"bg2"},
  thael_zaki: {name:"Zaki", game:"bg2"},
  tod_tian: {name:"Tian", game:"bg2"},
  travellers_laure: {name:"Laure", game:"bg2"},
  ts_sime: {name:"Sime (Vlad)", game:"bg2", recruitable:true},
  valkrana: {name:"Valkrana", game:"bg2", recruitable:true},
  varshoon: {name:"Varshoon", game:"bg2", recruitable:true},
  verrsza: {name:"Verr'Sza", game:"bg2", recruitable:true},
  walahnan: {name:"Walahnan", game:"bg2", recruitable:true},
  white_npc: {name:"White", game:"bg1", recruitable:true},
  xardas: {name:"Xardas", game:"bg2", recruitable:true},
  xulaye: {name:"Xulaye", game:"bg2", recruitable:true},
  yasraena: {name:"Yasraena", game:"bg2", recruitable:true},
  zaiya: {name:"Zaiya", game:"bg2", recruitable:true},
  zakrion: {name:"Zakrion", game:"both", recruitable:true},
  zakrion_bu: {name:"Zakrion (Undead)", game:"bg2"},
  zelink: {name:"Zelink", game:"bg2", recruitable:true},
};

// Add default portrait paths from existing pt data
fs.readdirSync('./data/mods').forEach(f => {
  if (!f.endsWith('.json') || f === '_catalog.json') return;
  const data = JSON.parse(fs.readFileSync(path.join('./data/mods', f)));
  if (!data.pt || !data.pt.npc) return;
  for (const entries of Object.values(data.pt.npc)) {
    for (const [npcId, imgPath, phase] of entries) {
      if (newEntries[npcId] && !newEntries[npcId].default) {
        newEntries[npcId].default = imgPath;
      }
    }
  }
});

let added = 0;
for (const [id, entry] of Object.entries(newEntries)) {
  if (!(id in npcs)) {
    npcs[id] = entry;
    added++;
  }
}

fs.writeFileSync('./data/npcs.json', JSON.stringify(npcs, null, 2));
console.log('Added ' + added + ' NPC entries to npcs.json');
console.log('Total npcs.json entries: ' + Object.keys(npcs).length);
