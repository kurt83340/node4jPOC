// Carte de paramètres de cypher/anglais/renommer.cypher (spec 002, plan D8), produite
// depuis correspondance.toml par `uv run --directory banc python -m banc anglais` :
// ne pas l'éditer. scripts/charger.sh --schema la passe à cypher-shell (-P), sans ses
// lignes « // » ; $langue choisit le sens.
{cartes: {
  en: {
    labels: {
      Forme: 'Form',
      Talent: 'Ability',
      Attaque: 'Move'
    },
    types: {
      A_POUR_FORME_PAR_DEFAUT: 'HAS_DEFAULT_FORM',
      FORME_DE: 'FORM_OF',
      EVOLUE_EN: 'EVOLVES_INTO',
      A_LE_TYPE: 'HAS_TYPE',
      SUPER_EFFICACE_CONTRE: 'SUPER_EFFECTIVE_AGAINST',
      PEU_EFFICACE_CONTRE: 'NOT_VERY_EFFECTIVE_AGAINST',
      SANS_EFFET_CONTRE: 'NO_EFFECT_AGAINST',
      A_LE_TALENT: 'HAS_ABILITY',
      APPREND: 'LEARNS',
      A_POUR_DESCRIPTION: 'HAS_DESCRIPTION'
    },
    cles: {
      identifiantPokeapi: 'pokeapiIdentifier',
      nom: 'name',
      categorie: 'category',
      parDefaut: 'isDefault',
      statPv: 'statHp',
      statAttaque: 'statAttack',
      statAttaqueSpeciale: 'statSpecialAttack',
      statDefenseSpeciale: 'statSpecialDefense',
      statVitesse: 'statSpeed',
      puissance: 'power',
      precision: 'accuracy',
      texte: 'text',
      jeux: 'games',
      rang: 'slot',
      facteur: 'factor',
      cache: 'isHidden',
      methodes: 'methods',
      niveau: 'level'
    }
  },
  fr: {
    labels: {
      Form: 'Forme',
      Ability: 'Talent',
      Move: 'Attaque'
    },
    types: {
      HAS_DEFAULT_FORM: 'A_POUR_FORME_PAR_DEFAUT',
      FORM_OF: 'FORME_DE',
      EVOLVES_INTO: 'EVOLUE_EN',
      HAS_TYPE: 'A_LE_TYPE',
      SUPER_EFFECTIVE_AGAINST: 'SUPER_EFFICACE_CONTRE',
      NOT_VERY_EFFECTIVE_AGAINST: 'PEU_EFFICACE_CONTRE',
      NO_EFFECT_AGAINST: 'SANS_EFFET_CONTRE',
      HAS_ABILITY: 'A_LE_TALENT',
      LEARNS: 'APPREND',
      HAS_DESCRIPTION: 'A_POUR_DESCRIPTION'
    },
    cles: {
      pokeapiIdentifier: 'identifiantPokeapi',
      name: 'nom',
      category: 'categorie',
      isDefault: 'parDefaut',
      statHp: 'statPv',
      statAttack: 'statAttaque',
      statSpecialAttack: 'statAttaqueSpeciale',
      statSpecialDefense: 'statDefenseSpeciale',
      statSpeed: 'statVitesse',
      power: 'puissance',
      accuracy: 'precision',
      text: 'texte',
      games: 'jeux',
      slot: 'rang',
      factor: 'facteur',
      isHidden: 'cache',
      methods: 'methodes',
      level: 'niveau'
    }
  }
}}
