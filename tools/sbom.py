"""Deterministic SPDX 2.3 inventory of retained release inputs, not the target OS."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import uuid
from recovery import MANIFEST, digest


def generate(root):
    root=Path(root)
    manifest=json.loads((root/MANIFEST).read_text())
    version=(root/'VERSION').read_text().strip()
    namespace=uuid.uuid5(uuid.NAMESPACE_URL,digest(root/MANIFEST)+version)
    created=datetime.datetime.fromtimestamp(int(os.environ.get('SOURCE_DATE_EPOCH','1793383200')),datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    packages=[];relationships=[]
    for item in manifest['artifacts']:
        identifier='SPDXRef-'+re.sub(r'[^A-Za-z0-9.-]','-',item['kind']+'-'+item['name'])
        name=item['name'];pkg_version=item.get('version')
        if item['kind']=='wheel':name,pkg_version=name.split('-')[:2]
        package=dict(name=name,SPDXID=identifier,versionInfo=pkg_version,
                     downloadLocation=item.get('source_url','NOASSERTION'),
                     filesAnalyzed=False,licenseConcluded='NOASSERTION',
                     licenseDeclared='NOASSERTION',copyrightText='NOASSERTION',
                     checksums=[dict(algorithm='SHA256',checksumValue=item['sha256'])],
                     sourceInfo='Retained release input: '+item['file'])
        packages.append(package)
        relationships.append(dict(spdxElementId='SPDXRef-DOCUMENT',relationshipType='DESCRIBES',relatedSpdxElement=identifier))
    return dict(spdxVersion='SPDX-2.3',dataLicense='CC0-1.0',SPDXID='SPDXRef-DOCUMENT',
                name='HyprlandFiles '+version+' retained release inputs',
                documentNamespace='https://github.com/abhisekupadhyaya/HyprlandFiles/spdx/'+str(namespace),
                creationInfo=dict(creators=['Tool: HyprlandFiles-sbom-'+version],created=created),
                comment='Inventory of the 33 retained desktop/greeter/wheel artifacts only. Excludes source files, transitive target OS packages and firmware. NOASSERTION licensing requires upstream review before binary publication.',
                packages=packages,relationships=relationships)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    a=parser.parse_args();root=Path(__file__).resolve().parents[1]
    target=root/'docs/release-inputs.spdx.json'
    text=json.dumps(generate(root),indent=2)+'\n'
    if a.check:
        if not target.is_file() or target.read_text()!=text:raise SystemExit('Release input SBOM is stale; regenerate and review')
        print('Release input SPDX inventory matches the recovery manifest')
    else:
        target.write_text(text);print('Generated '+str(target))
