"use strict";
// Interface de la Pharmacie. Toutes les adresses sont relatives : l'application vit derrière l'ingress de HA.

const page = document.getElementById("page");
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sansAccent = (t) => String(t).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

async function api(chemin, methode = "GET", corps) {
  const options = { method: methode };
  if (corps !== undefined) {
    options.body = JSON.stringify(corps);
    options.headers = { "Content-Type": "application/json" };
  }
  const rep = await fetch("api/" + chemin, options);
  const donnees = await rep.json().catch(() => ({}));
  if (!rep.ok) throw new Error(donnees.erreur || "Une erreur est survenue");
  return donnees;
}

const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
const moisLisible = (p) => { const [a, m] = p.split("-"); return `${MOIS[+m - 1]} ${a}`; };

const ETIQUETTES = { perime: "Périmé", bientot: "Bientôt", inconnu: "Date ?", epuise: "Épuisé", ouvert_trop_longtemps: "À vérifier" };

function carteProduit(p) {
  const details = p.raison || [p.dosage, p.forme, p.emplacement, p.peremption && `exp. ${moisLisible(p.peremption)}`].filter(Boolean).join(" · ");
  const quantite = p.quantite > 1 ? ` <span class="doux">× ${p.quantite}</span>` : "";
  const etat = ETIQUETTES[p.etat] ? `<span class="etat ${p.etat}">${ETIQUETTES[p.etat]}</span>` : "";
  const photo = p.photo ? `<img src="${esc(p.photo)}" alt="">` : "";
  return `<a class="produit" href="#/produit/${p.id}">${photo}
    <span class="corps"><span class="nom">${esc(p.nom)}${quantite}</span><br><span class="details">${esc(details)}</span></span>${etat}</a>`;
}

const numeros = (liste) => `<div class="numeros">${liste.map((n) => `
  <a class="numero" href="tel:${esc(n.numero.replace(/\s/g, ""))}"><b>${esc(n.numero)}</b>
  <span><strong>${esc(n.nom)}</strong>${esc(n.detail)}</span></a>`).join("")}</div>`;

// ---------------------------------------------------------------- J'ai mal
async function vueMaux() {
  const frais = await api("maux");
  page.innerHTML = `
    <h1>Qu'est-ce qui ne va pas ?</h1>
    <input class="recherche" id="q" type="search" placeholder="Mal de tête, toux, piqûre…" aria-label="Chercher un mal" autocomplete="off">
    <p class="avis">Conseils pour adultes. Enfant, grossesse ou allaitement : demandez d'abord au pharmacien ou au médecin.</p>
    <div id="liste"></div>
    <h2>En cas d'urgence</h2>
    ${numeros(frais.urgence)}
    <p class="doux" style="margin-top:10px">Pharmacie de garde : <a href="${esc(frais.garde)}" target="_blank" rel="noopener">pharmacie.be</a></p>`;
  const liste = document.getElementById("liste");
  const afficher = (texte) => {
    const q = sansAccent(texte.trim());
    const correspond = (m) => !q || sansAccent(m.nom + " " + m.mots.join(" ")).includes(q);
    const html = frais.groupes.map((g) => {
      const maux = frais.maux.filter((m) => m.groupe === g && correspond(m));
      if (!maux.length) return "";
      return `<h2>${esc(g)}</h2><div class="maux">${maux.map((m) =>
        `<a class="mal ${m.disponible ? "dispo" : ""}" href="#/mal/${m.cle}"><i></i>${esc(m.nom)}<span class="sr" hidden>${m.disponible ? "disponible" : ""}</span></a>`).join("")}</div>`;
    }).join("");
    liste.innerHTML = html ? html + `<p class="doux legende"><i></i>Vous avez de quoi le soulager</p>`
      : `<p class="vide">Rien pour « ${esc(texte)} ». En cas de doute, demandez au pharmacien.</p>`;
  };
  afficher("");
  document.getElementById("q").addEventListener("input", (e) => afficher(e.target.value));
}

function blocSubstance(s, cle) {
  const duree = s.duree ? `<p class="duree">${esc(s.duree)}</p>` : "";
  const precautions = s.precautions.length ? `<details><summary>Précautions</summary><ul>${s.precautions.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></details>` : "";
  const avis = s.sur_avis ? `<p class="duree">À utiliser seulement sur avis médical.</p>` : "";
  const produits = s.produits.length ? s.produits.map(carteProduit).join("") : `
    <div class="manque"><span>Pas dans votre armoire</span>
    ${s.sur_avis ? "" : `<button class="petit" data-acheter="${esc(s.nom)}" type="button">À acheter</button>`}</div>`;
  return `<div class="substance"><h3>${esc(s.nom)}</h3><p class="role">${esc(s.role)}</p>${avis}${produits}${duree}${precautions}</div>`;
}

async function vueMal(cle) {
  const m = await api("maux/" + cle);
  const urgence = m.urgence.length ? `<div class="encart urgence"><h3>Appelez le 112 si :</h3><ul>${m.urgence.map((t) => `<li>${esc(t)}</li>`).join("")}</ul><a class="tel" href="tel:112">Appeler le 112</a></div>` : "";
  const consulter = m.consulter.length ? `<div class="encart consulter"><h3>Consultez un médecin si :</h3><ul>${m.consulter.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></div>` : "";
  const cumul = m.cumul.map((c) => `<div class="encart urgence"><h3>Ne cumulez pas</h3><p>${c.produits.map(esc).join(" et ")} sont de la même famille (${esc(c.substance)}). N'en prenez qu'un à la fois.</p></div>`).join("");
  const ecarter = m.a_ecarter.length ? `<h2>À ne pas prendre sans avis</h2><div class="liste">${m.a_ecarter.map(carteProduit).join("")}</div>` : "";
  const perso = m.perso.length ? `<h2>Vous l'avez associé à ce mal</h2><p class="doux">Votre propre choix, non vérifié par ce guide.</p><div class="liste">${m.perso.map(carteProduit).join("")}</div>` : "";
  const rien = !m.principal.length ? `<div class="encart ok"><p>Aucun médicament n'est à privilégier ici : commencez par les gestes ci-dessous.</p></div>` : "";
  page.innerHTML = `
    <a class="retour" href="#/">‹ Tous les maux</a>
    <h1>${esc(m.nom)}</h1>
    ${urgence}${consulter}
    <h2>Quoi faire</h2>
    <ul>${m.gestes.map((g) => `<li>${esc(g)}</li>`).join("")}</ul>
    <h2>Quoi utiliser</h2>
    <p class="doux">La dose est sur la notice : lisez-la, même pour un produit habituel.</p>
    ${cumul}${rien}
    ${m.principal.map((s) => blocSubstance(s)).join("")}
    ${m.aussi.length ? `<h2>Autres possibilités</h2>${m.aussi.map((s) => blocSubstance(s)).join("")}` : ""}
    ${perso}${ecarter}
    <p class="avis">Doute, traitement en cours, allergie, maladie chronique, grossesse ou allaitement : demandez au pharmacien avant de prendre quoi que ce soit.</p>`;
  page.querySelectorAll("[data-acheter]").forEach((b) => b.addEventListener("click", async () => {
    await api("courses", "POST", { libelle: b.dataset.acheter });
    b.textContent = "Ajouté ✓";
    b.disabled = true;
    majPastille();
  }));
}

// ---------------------------------------------------------------- Armoire
async function vueArmoire() {
  const produits = await api("produits");
  const groupes = [
    ["tous", "Tous", () => true],
    ["perime", "Périmés", (p) => p.etat === "perime"],
    ["bientot", "Bientôt", (p) => p.etat === "bientot"],
    ["verifier", "À vérifier", (p) => p.etat === "inconnu" || p.etat === "ouvert_trop_longtemps"],
    ["epuise", "Épuisés", (p) => p.etat === "epuise"],
  ];
  page.innerHTML = `
    <div class="entete"><h1>Armoire</h1><a class="bouton principal" href="#/produit/nouveau">+ Ajouter</a></div>
    ${produits.length ? `
      <input class="recherche" id="q" type="search" placeholder="Chercher un produit ou une substance" aria-label="Chercher dans l'armoire" autocomplete="off">
      <div class="bilan" id="filtres" style="margin-top:10px"></div>
      <div class="liste" id="liste"></div>` : `
      <p class="vide">Votre armoire est encore vide. Photographiez une première boîte : l'IA de Home Assistant lira le nom et la date.</p>`}`;
  if (!produits.length) return;
  let filtre = "tous";
  let texte = "";
  const afficher = () => {
    const f = groupes.find((g) => g[0] === filtre)[2];
    const q = sansAccent(texte.trim());
    const garde = produits.filter((p) => f(p) && (!q || sansAccent([p.nom, p.substances_texte, p.emplacement, ...p.substances_noms].join(" ")).includes(q)));
    document.getElementById("liste").innerHTML = garde.map(carteProduit).join("") || `<p class="vide">Aucun produit ici.</p>`;
    document.getElementById("filtres").innerHTML = groupes.map(([cle, nom, fn]) => {
      const n = produits.filter(fn).length;
      return n || cle === "tous" ? `<button type="button" data-f="${cle}" aria-pressed="${filtre === cle}">${nom} (${n})</button>` : "";
    }).join("");
  };
  document.getElementById("filtres").addEventListener("click", (e) => {
    const b = e.target.closest("[data-f]");
    if (b) { filtre = b.dataset.f; afficher(); }
  });
  document.getElementById("q").addEventListener("input", (e) => { texte = e.target.value; afficher(); });
  afficher();
}

// ---------------------------------------------------------------- Fiche d'un produit
function reduire(fichier, cote, qualite) {
  return new Promise((resoudre, rejeter) => {
    const url = URL.createObjectURL(fichier);
    const img = new Image();
    img.onload = () => {
      const echelle = Math.min(1, cote / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * echelle);
      c.height = Math.round(img.height * echelle);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      resoudre(c.toDataURL("image/jpeg", qualite));
    };
    img.onerror = () => { URL.revokeObjectURL(url); rejeter(new Error("Cette image ne peut pas être lue")); };
    img.src = url;
  });
}

async function vueProduit(id) {
  const nouveau = id === "nouveau";
  const [ref, maux, tous] = await Promise.all([api("substances"), api("maux"), api("produits")]);
  const p = nouveau ? { nom: "", substances_texte: "", substances: [], maux_perso: [], dosage: "", forme: "", quantite: 1, peremption: "", ouvert_le: "", emplacement: "", notes: "", photo: "" } : await api("produits/" + id);
  const lieux = [...new Set(tous.map((x) => x.emplacement).filter(Boolean))];
  const coche = (nomGroupe, cle, nom, actif) => `<label><input type="checkbox" name="${nomGroupe}" value="${esc(cle)}" ${actif ? "checked" : ""}>${esc(nom)}</label>`;
  const conserver = !nouveau && (p.etat === "perime") ? `<div class="message erreur">Ce produit est périmé : ne l'utilisez plus et rapportez-le à la pharmacie.</div>` : "";
  const alertes = (p.alertes || []).map((a) => `<div class="message erreur">${esc(a)}.</div>`).join("");
  page.innerHTML = `
    <a class="retour" href="#/armoire">‹ Armoire</a>
    <h1>${nouveau ? "Ajouter un produit" : esc(p.nom)}</h1>
    <form id="f" novalidate>
      ${conserver}${alertes}
      ${ref.ia ? `<div class="scan">
        <strong>Photographier la boîte</strong>
        <span class="doux">Prenez aussi le côté où la date est imprimée. Les photos partent vers l'IA de Home Assistant, puis sont effacées.</span>
        <div class="vignettes" id="vignettes"></div>
        <label class="bouton"><input id="photos" type="file" accept="image/*" capture="environment"><span>Prendre une photo</span></label>
        <button type="button" id="lire" hidden>Lire les photos</button>
      </div>` : ""}
      <div id="retour" role="status"></div>
      <label>Nom<input name="nom" required value="${esc(p.nom)}" autocomplete="off"></label>
      <label>Substances écrites sur la boîte<input name="substances_texte" value="${esc(p.substances_texte)}" placeholder="Paracétamol" autocomplete="off"></label>
      <div class="deux">
        <label>Dosage<input name="dosage" value="${esc(p.dosage)}" placeholder="500 mg" autocomplete="off"></label>
        <label>Forme<select name="forme"><option value=""></option>${ref.formes.map((f) => `<option ${f === p.forme ? "selected" : ""}>${esc(f)}</option>`).join("")}</select></label>
      </div>
      <div class="deux">
        <label>Péremption<input name="peremption" type="month" value="${esc(p.peremption)}"></label>
        <div class="champ"><span>Boîtes</span><div class="compteur">
          <button type="button" id="moins" aria-label="Une boîte de moins">−</button>
          <output id="quantite">${p.quantite}</output>
          <button type="button" id="plus" aria-label="Une boîte de plus">+</button></div></div>
      </div>
      <div class="deux">
        <label>Ouvert le<input name="ouvert_le" type="date" value="${esc(p.ouvert_le)}"></label>
        <label>Emplacement<input name="emplacement" list="lieux" value="${esc(p.emplacement)}" placeholder="Salle de bain" autocomplete="off"><datalist id="lieux">${lieux.map((l) => `<option value="${esc(l)}">`).join("")}</datalist></label>
      </div>
      <label>Notes<textarea name="notes">${esc(p.notes)}</textarea></label>
      <details class="choix"><summary>Reconnu comme : <span id="reconnu"></span></summary>
        <p class="doux" style="margin:8px 0 0">Corrigez si besoin : c'est ce qui relie le produit aux maux.</p>
        <div class="coches">${ref.substances.map((s) => coche("substances", s.cle, s.nom, p.substances.includes(s.cle))).join("")}</div>
      </details>
      <details class="choix"><summary>Associer à un mal, à ma façon</summary>
        <p class="doux" style="margin:8px 0 0">Pour un produit que ce guide ne connaît pas. Ce lien ne sera pas vérifié.</p>
        <div class="coches">${maux.maux.map((m) => coche("maux_perso", m.cle, m.nom, p.maux_perso.includes(m.cle))).join("")}</div>
      </details>
      <div id="erreur" role="alert"></div>
      <div class="actions">
        <button class="principal" type="submit">Enregistrer</button>
        ${nouveau ? "" : `<button class="danger" type="button" id="supprimer">Retirer de l'armoire</button>`}
      </div>
    </form>`;

  const f = document.getElementById("f");
  const sortie = document.getElementById("quantite");
  let quantite = p.quantite;
  let vignette = p.photo;
  const photos = [];
  const coches = () => [...f.querySelectorAll('[name="substances"]:checked')];
  const majReconnu = () => {
    document.getElementById("reconnu").textContent = coches().map((c) => c.parentElement.textContent.trim()).join(", ") || "rien pour l'instant";
  };
  majReconnu();
  f.querySelectorAll('[name="substances"]').forEach((c) => c.addEventListener("change", majReconnu));
  document.getElementById("plus").onclick = () => { sortie.textContent = quantite = Math.min(999, quantite + 1); };
  document.getElementById("moins").onclick = () => { sortie.textContent = quantite = Math.max(0, quantite - 1); };

  const retour = document.getElementById("retour");
  if (ref.ia) {
    const bLire = document.getElementById("lire");
    document.getElementById("photos").addEventListener("change", async (e) => {
      const fichier = e.target.files[0];
      e.target.value = "";
      if (!fichier) return;
      try {
        photos.push(await reduire(fichier, 1600, 0.85));
        if (!vignette) vignette = await reduire(fichier, 160, 0.7);
        document.getElementById("vignettes").innerHTML = photos.map((src) => `<img src="${src}" alt="Photo de la boîte">`).join("");
        if (photos.length >= 3) e.target.closest("label").hidden = true;
        bLire.hidden = false;
      } catch (err) {
        retour.innerHTML = `<div class="message erreur">${esc(err.message)}</div>`;
      }
    });
    bLire.addEventListener("click", async () => {
      bLire.disabled = true;
      bLire.textContent = "Lecture en cours…";
      try {
        const r = await api("lire-boite", "POST", { photos });
        for (const c of ["nom", "substances_texte", "dosage", "forme", "peremption"]) {
          if (r[c]) f.elements[c].value = r[c];
        }
        f.querySelectorAll('[name="substances"]').forEach((c) => { c.checked = r.substances.includes(c.value); });
        majReconnu();
        const date = r.peremption ? "" : " La date n'a pas pu être lue : indiquez-la.";
        retour.innerHTML = `<div class="message info">Vérifiez ces informations, surtout la date, avant d'enregistrer.${date}</div>`;
      } catch (err) {
        retour.innerHTML = `<div class="message erreur">${esc(err.message)} Vous pouvez remplir la fiche à la main.</div>`;
      }
      bLire.disabled = false;
      bLire.textContent = "Relire les photos";
    });
  }

  f.addEventListener("submit", async (e) => {
    e.preventDefault();
    const erreur = document.getElementById("erreur");
    const v = f.elements;
    const corps = { quantite, photo: vignette || "" };
    for (const c of ["nom", "substances_texte", "dosage", "forme", "peremption", "ouvert_le", "emplacement", "notes"]) corps[c] = v[c].value;
    corps.substances = coches().map((c) => c.value);
    corps.maux_perso = [...f.querySelectorAll('[name="maux_perso"]:checked')].map((c) => c.value);
    // Rien de coché sur une fiche neuve : le serveur déduit les substances du texte et du nom.
    if (nouveau && !corps.substances.length) delete corps.substances;
    if (!corps.nom.trim()) {
      erreur.innerHTML = `<div class="message erreur">Le nom du produit est obligatoire.</div>`;
      v.nom.focus();
      return;
    }
    try {
      await (nouveau ? api("produits", "POST", corps) : api("produits/" + id, "PUT", corps));
      location.hash = "#/armoire";
    } catch (err) {
      erreur.innerHTML = `<div class="message erreur">${esc(err.message)}</div>`;
    }
  });

  const bSupprimer = document.getElementById("supprimer");
  if (bSupprimer) bSupprimer.addEventListener("click", async () => {
    if (!confirm(`Retirer « ${p.nom} » de l'armoire ?`)) return;
    await api("produits/" + id, "DELETE");
    location.hash = "#/armoire";
  });
}

// ---------------------------------------------------------------- À racheter
async function vueCourses() {
  const r = await api("resume");
  const lignes = (liste) => `<div class="liste">${liste.map(carteProduit).join("")}</div>`;
  const manquants = r.essentiels.filter((e) => !e.present);
  page.innerHTML = `
    <h1>À racheter</h1>
    ${r.perimes.length ? `<h2>Périmés</h2><p class="doux">À rapporter à la pharmacie, puis à retirer de l'armoire. Ne les jetez ni à la poubelle ni dans l'évier.</p>${lignes(r.perimes)}` : ""}
    ${r.epuises.length ? `<h2>Épuisés</h2>${lignes(r.epuises)}` : ""}
    ${r.bientot.length ? `<h2>Périment bientôt</h2>${lignes(r.bientot)}` : ""}
    ${r.a_verifier.length ? `<h2>À vérifier</h2>${lignes(r.a_verifier)}` : ""}
    <h2>Ma liste</h2>
    <div id="courses">${r.courses.map((c) => `<div class="article"><span>${esc(c.libelle)}</span><button class="petit" type="button" data-retirer="${c.id}">Acheté</button></div>`).join("") || `<p class="doux">Rien pour l'instant.</p>`}</div>
    <form class="ajout" id="ajout"><input name="libelle" placeholder="Ajouter un produit" aria-label="Produit à acheter" autocomplete="off"><button type="submit">Ajouter</button></form>
    <h2>Trousse de base</h2>
    <p class="doux">${manquants.length ? `Il vous manque ${manquants.length} produit${manquants.length > 1 ? "s" : ""} sur ${r.essentiels.length}.` : "Tout y est."}</p>
    ${r.essentiels.map((e) => `<div class="essentiel"><span>${esc(e.nom)}</span>${e.present ? `<span class="ok" aria-label="Présent">✓</span>` : `<button class="petit" type="button" data-acheter="${esc(e.nom)}">À acheter</button>`}</div>`).join("")}
    <p class="doux" style="margin-top:16px"><a href="api/export.json" download="pharmacie.json">Exporter l'armoire</a></p>`;
  page.querySelectorAll("[data-retirer]").forEach((b) => b.addEventListener("click", async () => {
    await api("courses/" + b.dataset.retirer, "DELETE");
    majPastille();
    vueCourses();
  }));
  page.querySelectorAll("[data-acheter]").forEach((b) => b.addEventListener("click", async () => {
    await api("courses", "POST", { libelle: b.dataset.acheter });
    majPastille();
    vueCourses();
  }));
  document.getElementById("ajout").addEventListener("submit", async (e) => {
    e.preventDefault();
    const v = e.target.elements.libelle.value.trim();
    if (!v) return;
    await api("courses", "POST", { libelle: v });
    majPastille();
    vueCourses();
  });
}

// ---------------------------------------------------------------- Navigation
async function majPastille() {
  try {
    const r = await api("resume");
    const n = r.perimes.length + r.epuises.length + r.courses.length;
    const b = document.getElementById("pastille");
    b.textContent = n;
    b.hidden = !n;
  } catch { /* la pastille n'est pas essentielle */ }
}

async function naviguer() {
  const route = location.hash.replace(/^#\/?/, "").split("/");
  const onglet = { armoire: "armoire", produit: "armoire", courses: "courses" }[route[0]] || "maux";
  document.querySelectorAll(".onglets a").forEach((a) => {
    const actif = a.dataset.onglet === onglet;
    a.classList.toggle("actif", actif);
    if (actif) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  try {
    if (route[0] === "mal" && route[1]) await vueMal(route[1]);
    else if (route[0] === "armoire") await vueArmoire();
    else if (route[0] === "produit" && route[1]) await vueProduit(route[1]);
    else if (route[0] === "courses") await vueCourses();
    else await vueMaux();
  } catch (err) {
    page.innerHTML = `<div class="message erreur">${esc(err.message)}</div>`;
  }
  scrollTo(0, 0);
  majPastille();
}

addEventListener("hashchange", naviguer);
naviguer();
