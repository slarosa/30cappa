# -*- coding: utf-8 -*-
"""30cappa.ipynb


# 30cappa con meno di 5mila abitanti

![](https://raw.githubusercontent.com/aborruso/30cappa/main/risorse/2020-12-18_slide_Natale.png)

- trovare i piccoli Comuni (fino a 5mila abitanti)
- calcolare i 30kmdal confine  da cui possono spostare
- impedendo di andare nei Comuni capoluogo di Provincia

uno script creato da [@napo](https://twitter.com/napo) e distribuito con licenza [WTFPL](https://it.wikipedia.org/wiki/WTFPL)

## Setup

queste istruzoni possono essere commentate
"""

import pandas as pd
import geopandas as gpd
import os
import requests, zipfile, io
import matplotlib.pyplot as plt
import contextily as ctx
import datetime
from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry import *
import json
pd.options.mode.chained_assignment = None

"""# Raccolta dei dati
- confini comunali
- statistiche popolazione

## Confini dei comuni d'Italia

ISTAT offre gli shapefile delle unità amministrative
https://www.istat.it/it/archivio/222527

Ciascun archivio è un file zip che contiene diverse unità amministrative: macroregioni, regioni, province e comuni.
Alcuni campi significativi:
- PRO_COM_T è il codice univoco per ogni comune assegnato da ISTAT
- *CC_UTS* quando il valore è uguale a 1 significa che si tratta di un comune capoluogo di provincia
- *COD_REG* è il codice univoco della regione assegnato da ISTAT

**NOTE**<br/>
- le geometrie dei confini comunali sono archiviate con proiezione [WGS 84 / UTM zone 32N](https://epsg.io/32632), quindi in metri
- molti comuni hanno [enclave ed exclave](https://it.wikipedia.org/wiki/Enclave_ed_exclave) con il risultato che il confine comunale è composto da aree non contigue fra di loro
- un caso particolare è il comune di [Campione d'Italia](https://it.wikipedia.org/wiki/Campione_d%27Italia) che è al di fuori dal confine italiano
- le province autonome di Trento e Bolzano, in questo caso, vanno considerate come regioni, quindi bisogna guardare anche il valore *COD_PROV*.la Regione Trentino Alto Adige ha COD_REG con valore 4, la provincia di Bolzano ha valore COD_PROV=21 mentre Trento COD_PROV=22


**download dei dati**
"""

# indirizzo del file
zip_file_url = 'https://www.istat.it/storage/cartografia/confini_amministrativi/non_generalizzati/Limiti01012020.zip'
zip_file_url = 'https://www.istat.it/storage/cartografia/confini_amministrativi/generalizzati/Limiti01012020_g.zip'
#download
r = requests.get(zip_file_url)
z = zipfile.ZipFile(io.BytesIO(r.content))
#decompressione
z.extractall()

"""**geodataframe con i limiti comunali**"""

limiti_comuni = gpd.read_file("Limiti01012020_g" + os.sep + "Com01012020_g" + os.sep + "Com01012020_g_WGS84.shp",encoding='utf-8')


"""**creazione del confine nazionale**
questo servirà per tagliare le aree all'interno del confine nazionale.<br/>
Per creare il confine partiamo dal file con le macroregioni d'Italia solo per questioni di performance
"""

macroregioni_italiane = gpd.read_file("Limiti01012020_g" + os.sep + "RipGeo01012020_g" + os.sep + "RipGeo01012020_g_WGS84.shp",encoding='utf-8')

"""creiamo un campo per creare la dissolvenza ( = unire tutti i poligoni con lo stesso valore)"""

macroregioni_italiane['nazione']='Italia'

confini_italia = macroregioni_italiane[['nazione', 'geometry']]

"""... ed ora procediamo con la dissolvenza"""

confini_italia = confini_italia.dissolve(by='nazione')

"""**ottenere l'elenco dei capoluoghi di provincia**

CC_UTS = 1
"""

comuni_capoluoogo_provincia = limiti_comuni[limiti_comuni.CC_UTS == 1][['COMUNE','PRO_COM_T','COD_REG','geometry']]

# visualizzare i primi 5
comuni_capoluoogo_provincia.head(5)

"""## Informazioni statistiche sulla popolazione in Italia

ISTAT offre il sito https://demo.istat.it che rilascia dati aggiornati con cadenza periodica.

L'ultimo elenco disponibile è quello di gennaio 2020

Il file con i dati per comune si trova qui http://demo.istat.it/pop2020/dati/comuni.zip
"""

dati_demografici_comuni_italiani = "http://demo.istat.it/pop2020/dati/comuni.zip"

"""nonostante lo zip contenga un CSV la prima riga va cancellata in quanto è usata come titolo del dataset, pertanto bisogna partire dalla seconda (*skiprows=1*).<br/>
La codifica caratteri è *utf-8*

**alternativa**

per ottenere quelli da dopo gennaio 2020 bisogna scaricare una tavola alla volta per provincia

l'url è questa<br/>
http://demo.istat.it/bilmens/query1.php?lingua=ita&allrp=4&Pro=84&periodo=8&anno=2020&submit2=Salva


Pro => valore della provincia<br/>
periodo => mese<br/>
anno => anno
"""

demo_comuni = pd.read_csv(dati_demografici_comuni_italiani,skiprows=1,encoding='utf-8',low_memory=False)


"""**note**<br/>
ogni riga è organizzata per fasce d'età (campo *Età*), il valore *999* contiene il totale.<br/>
Occorre quindi filtrare il csv per il valore *999*


quindi è necessario filtrare per quel valore
"""

comuni_popolazione = demo_comuni[demo_comuni.Età == 999]

"""per calcolare il totale della popolazione è necessario sommare *Totale Femmine* con *Totale Maschi*"""

def totalepopolazione(maschi,femmine):
  totale = int(maschi) +int(femmine)
  return(totale)

comuni_popolazione['POPOLAZIONE'] = comuni_popolazione.apply(lambda row: totalepopolazione(row['Totale Femmine'], row['Totale Maschi']), axis=1)

"""dalla tabella creata prendiamo solo le colonne utili

"""

comuni_popolazione = comuni_popolazione[['Codice comune','Denominazione','POPOLAZIONE']]

"""per comodità nelle operazioni successive conviene rinominare le colonne allo stesso modo di quelle del file con i confini comunali"""

comuni_popolazione.rename(columns={'Codice comune':'PRO_COM_T','Denominazione':'COMUNE'}, inplace=True)

"""i codici istat sono stringhe di 6 caratteri composte dal codice della provincia e un valore incrementale per ogni comune della provincia stessa.<Br/>
Per ottenere 6 caratteri si aggiungono degli zeri all'inizio
"""

comuni_popolazione['PRO_COM_T'] = comuni_popolazione.PRO_COM_T.apply(lambda k: str(k).zfill(6))

"""la tabella con i dati demografici di ISTAT non è aggiornata con i comuni che si sono uniti.<br/>
Occorre ricavare questa lista.

ANPR offre l'elenco di tutti i comuni d'Italia<br/>
Qui il file csv<br/>
https://www.anpr.interno.it/portale/documents/20182/50186/ANPR_archivio_comuni.csv
"""

anpr_comuni = pd.read_csv("https://www.anpr.interno.it/portale/documents/20182/50186/ANPR_archivio_comuni.csv")

anpr_comuni['PRO_COM_T'] = anpr_comuni['CODISTAT'].apply(lambda k: str(k).zfill(6))

codici_comuni_anpr = anpr_comuni['PRO_COM_T'].unique()

codici_comuni_confini = limiti_comuni.PRO_COM_T.unique()

codici_comune_popolazione = comuni_popolazione.PRO_COM_T.unique()

comuni_prefusione = set(codici_comune_popolazione) - set(codici_comuni_confini)

"""... questo è fatto a mano da wikipedia perchè non ho trovato tabelle che aiutano a farlo in automatico"""

fusioni = []
nuovo = {}
nuovo['COMUNE'] = 'NOVELLA'
nuovo['PRO_COM_T'] = '022253'
# Cloz, Revò, Cagnò, Brez, Romallo
excomuni=['022063','022152','022030','022027','022154']
nuovo['excomuni']=excomuni
fusioni.append(nuovo)
nuovo = {'COMUNE':"BORGO D'ANAUNIA"}
nuovo['PRO_COM_T'] = '022252'
# Castelfondo, Fondo, Malosco
excomuni=['022046','022088','022111']
nuovo['excomuni']=excomuni
fusioni.append(nuovo)
nuovo = {'COMUNE':"VILLE DI FIEMME"}
nuovo['PRO_COM_T'] = '022254'
# Carano, Daiano, Malosco
excomuni=['022041','022070','022211']
nuovo['excomuni']=excomuni
fusioni.append(nuovo)

for fusione in fusioni:
  row = {}
  abitanti = 0
  for da in fusione['excomuni']:
    abitanti += comuni_popolazione[comuni_popolazione.PRO_COM_T == da].POPOLAZIONE.values[0]
  row['COMUNE'] = fusione['COMUNE']
  row['PRO_COM_T'] = fusione['PRO_COM_T']
  row['POPOLAZIONE'] = abitanti
  comuni_popolazione = comuni_popolazione.append(row,ignore_index=True)

"""... cosi come i comuni annessi ad altri"""

daggiungere = []
daa = {}
# Faedo
daa['da'] = '022080'
# San Michele all'Adige
daa['a'] = '022167'
daggiungere.append(daa)
daa = {}
# Vendrogno
daa['da'] = '097085'
# Bellano
daa['a'] = '097008'

for aggiungi in daggiungere:
  da = aggiungi['da']
  a = aggiungi['a']
  abitanti_da = comuni_popolazione[comuni_popolazione.PRO_COM_T == da].POPOLAZIONE.values[0]
  abitanti_a = comuni_popolazione[comuni_popolazione.PRO_COM_T == a].POPOLAZIONE.values[0]
  comuni_popolazione[comuni_popolazione.PRO_COM_T == a].POPOLAZIONE = abitanti_da + abitanti_a

"""vanno rimossi i codici istat dei comuni che non esistono più causa fusione"""

excomuni = ['097085','022080','022063','022152','022030','022027','022154','022046','022088','022111','022041','022070','022211']

comuni_popolazione =comuni_popolazione[~comuni_popolazione.PRO_COM_T.isin(excomuni)]

"""**elenco dei 'piccoli Comuni'**

la definizione dice "fino a 5000 abitanti" 
"""

piccoli_comuni = comuni_popolazione[comuni_popolazione.POPOLAZIONE <= 5000]

"""esportazione del file in formato .csv"""

piccoli_comuni.to_csv("piccoli_comuni.csv")

"""## trovare l'area a 30km di raggio dal confine dei piccoli comuni

operazioni da svolgere:
- aggiungere ai dati dei confini comunali l'attributo della popolazione per ciascun comune
- l'area a 30cappa si calcola usando la funzione [buffer](https://geopandas.org/geometric_manipulations.html#GeoSeries.buffer)
- a questa va sottratta dei confini nazionali 

come output generiamo un file geojson per ogni comune e associamo anche la lista dei comuni a 30km di distanza nel campo *comunia30cappa*

estendere alle geometrie il valore della popolazione
"""

comuni_popolazione_tojoin = comuni_popolazione[['PRO_COM_T','POPOLAZIONE']]

"""per fare la join è necessario che entrambi i campi abbiano gli stessi valori.<br/> 
il codice ISTAT dei comuni è fatto da sei cifre ed è composto dal codice provincia più un numero sequenziale dei comuni presenti.<br/>
Per renderlo di 6 cifre si aggiungo tanti zero quanti necessari (funzione *zfill* di python)
"""

comuni_popolazione_tojoin['PRO_COM_T'] = comuni_popolazione_tojoin['PRO_COM_T'].apply(lambda k: str(k).zfill(6))


geo_comuni_popolazione = limiti_comuni.merge(comuni_popolazione_tojoin,on='PRO_COM_T')


"""genero un csv con tutti i nomi dei comuni, sigla della provincia, numero di abitanti e superfice"""

limiti_province = gpd.read_file("Limiti01012020_g" + os.sep + "ProvCM01012020_g" + os.sep + "ProvCM01012020_g_WGS84.shp",encoding='utf-8')

def sigla(cod_prov):
  sigla = limiti_province[limiti_province.COD_PROV == cod_prov].SIGLA.values[0]
  return(sigla)

geo_comuni_popolazione['SIGLA'] = geo_comuni_popolazione['COD_PROV'].apply(lambda cod_prov: sigla(cod_prov))

geo_comuni_popolazione['KM2'] =  round(geo_comuni_popolazione.geometry.area / 1000000,2)


popolazione = geo_comuni_popolazione[['PRO_COM_T','COMUNE','SIGLA','POPOLAZIONE','KM2']]

"""**comuni fino a 5000 abitanti e i loro confini**"""

geo_piccoli_comuni = geo_comuni_popolazione[geo_comuni_popolazione.POPOLAZIONE <= 5000]


"""**inizio del calcolo**

a causa del fatto che bisogna prendere in considerazione il confine regionale andiamo a fare il calcolo dei comuni per ogni regione (o provincia autonoma)

La fuzione *area30Cappa* si occupa di calcolare l'area di un singolo comune a 30km dal confine e genera anche un file geojson

"""

def area30Cappa(nome,geom,comuni_capoluogo,confine):
  # creazione dell'area a 30cappa dal confine
  # per ogni geometria (caso comuni su più poligoni)
  # creazione buffer
  geom = geom.buffer(30000)
  # interesezione con il confine italiano
  # qui mi basta solo la geometrai
  geom = geom.intersection(confine)
  # ciclo su tutti i capoluoghi di provincia
  for cg in comuni_capoluogo.values:
    # se si toccano
    if geom.intersects(cg.buffer(0)):
      # allora calcolo differenza con il poligono
      geom = geom.difference(cg.buffer(0))
  # creazione del file geojson
  nome = nome + ".geojson"
  comune = gpd.GeoDataFrame (
      None,
      crs='EPSG:32632',
      geometry=[geom]
  )
  comune.to_crs(epsg=4326).to_file(nome,driver="GeoJSON")
  return(geom)

"""estrazione delle geometrie dei confini

il confine italiano è in una sola geometria
"""

confini = confini_italia.geometry.values[0]

"""per i comuni capoluogo invece avrò un array"""

confini_comuni_capoluogo = comuni_capoluoogo_provincia.geometry

geo_piccoli_comuni_30cappa = geo_piccoli_comuni

# Commented out IPython magic to ensure Python compatibility.
geo_piccoli_comuni_30cappa['geometry'] = geo_piccoli_comuni_30cappa.apply(lambda row: area30Cappa(row.PRO_COM_T,row.geometry,confini_comuni_capoluogo,confini),axis=1)
# %time

"""genero il file geojson"""

#geo_piccoli_comuni_30cappa.to_file("piccolicomuni30cappa.geojson",driver="GeoJSON")
