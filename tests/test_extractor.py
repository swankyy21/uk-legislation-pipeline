from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from legislation_pipeline.extractor import CLMLExtractor
from legislation_pipeline.fetcher import normalise_url
from legislation_pipeline.serialisers import to_csv, to_html, to_json


CLML = """<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
    xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:dct="http://purl.org/dc/terms/"
    xmlns:atom="http://www.w3.org/2005/Atom"
    DocumentURI="http://www.legislation.gov.uk/ukpga/2024/15"
    IdURI="http://www.legislation.gov.uk/id/ukpga/2024/15"
    NumberOfProvisions="382"
    SchemaVersion="2.0"
    RestrictExtent="E+W+S+N.I."
    RestrictStartDate="2026-01-01">
  <ukm:Metadata>
    <dc:identifier>http://www.legislation.gov.uk/ukpga/2024/15</dc:identifier>
    <dc:title>Media Act 2024</dc:title>
    <dc:publisher>Statute Law Database</dc:publisher>
    <dc:modified>2026-01-16</dc:modified>
    <dc:contributor>Expert Participation</dc:contributor>
    <dct:valid>2026-01-01</dct:valid>
    <atom:link rel="self" href="http://www.legislation.gov.uk/ukpga/2024/15/data.xml" type="application/xml"/>
    <atom:link rel="alternate" type="application/pdf" href="http://www.legislation.gov.uk/ukpga/2024/15/data.pdf" title="PDF"/>
    <atom:link rel="alternate" type="application/rdf+xml" href="http://www.legislation.gov.uk/ukpga/2024/15/data.rdf" title="RDF/XML"/>
    <atom:link rel="http://purl.org/dc/terms/hasVersion" href="http://www.legislation.gov.uk/ukpga/2024/15/enacted" title="enacted"/>
    <atom:link rel="http://purl.org/dc/terms/hasVersion" href="http://www.legislation.gov.uk/ukpga/2024/15/2026-01-01" title="2026-01-01"/>
    <ukm:PrimaryMetadata>
      <ukm:DocumentClassification>
        <ukm:DocumentCategory Value="primary"/>
        <ukm:DocumentMainType Value="UnitedKingdomPublicGeneralAct"/>
        <ukm:DocumentStatus Value="revised"/>
      </ukm:DocumentClassification>
      <ukm:Year Value="2024"/>
      <ukm:Number Value="15"/>
      <ukm:EnactmentDate Date="2024-05-24"/>
      <ukm:ISBN Value="9780105702658"/>
      <ukm:UnappliedEffects>
        <ukm:UnappliedEffect EffectId="key-1" URI="http://www.legislation.gov.uk/id/effect/key-1"
            Type="coming into force"
            AffectingURI="http://www.legislation.gov.uk/id/uksi/2024/858"
            AffectedURI="http://www.legislation.gov.uk/id/ukpga/2024/15"
            AffectingProvisions="reg. 4(a)"
            AffectedProvisions="Sch. 2 para. 12(2)"
            Notes="source note"
            Comments="source comment"
            Modified="2024-08-22T12:07:58Z">
          <ukm:InForceDates>
            <ukm:InForce Applied="false" Prospective="true"/>
          </ukm:InForceDates>
        </ukm:UnappliedEffect>
      </ukm:UnappliedEffects>
    </ukm:PrimaryMetadata>
    <ukm:Alternatives>
      <ukm:Alternative URI="http://www.legislation.gov.uk/ukpga/2024/15/pdfs/ukpga_20240015_en.pdf" Date="2024-06-05" Size="2296694" Print="true"/>
    </ukm:Alternatives>
    <ukm:Statistics>
      <ukm:TotalParagraphs Value="385"/>
      <ukm:BodyParagraphs Value="154"/>
    </ukm:Statistics>
  </ukm:Metadata>
  <Primary>
    <PrimaryPrelims DocumentURI="http://www.legislation.gov.uk/ukpga/2024/15/introduction">
      <Title>Media Act 2024</Title>
      <LongTitle>An Act to make provision about public service television.</LongTitle>
    </PrimaryPrelims>
    <Body>
      <Part DocumentURI="http://www.legislation.gov.uk/ukpga/2024/15/part/1" IdURI="http://www.legislation.gov.uk/id/ukpga/2024/15/part/1" id="part-1">
        <Number>Part 1</Number>
        <Title>Public service television</Title>
        <P1group>
          <Title>Reports on the fulfilment of the public service remit</Title>
          <P1 DocumentURI="http://www.legislation.gov.uk/ukpga/2024/15/section/1" IdURI="http://www.legislation.gov.uk/id/ukpga/2024/15/section/1" id="section-1">
            <Pnumber>1</Pnumber>
          </P1>
        </P1group>
      </Part>
    </Body>
    <Schedules>
      <Schedule DocumentURI="http://www.legislation.gov.uk/ukpga/2024/15/schedule/1" IdURI="http://www.legislation.gov.uk/id/ukpga/2024/15/schedule/1" id="schedule-1">
        <Number>Schedule 1</Number>
        <Title>Schedule title</Title>
      </Schedule>
    </Schedules>
  </Primary>
  <Commentaries>
    <Commentary id="key-commentary" Type="I"><Para><Text>Section 1 in force.</Text></Para></Commentary>
  </Commentaries>
</Legislation>
"""


class ExtractorTests(unittest.TestCase):
    def test_extracts_real_clml_patterns(self) -> None:
        root = ET.fromstring(CLML)
        record = CLMLExtractor(root, source_url="https://www.legislation.gov.uk/ukpga/2024/15/data.xml").extract()

        self.assertEqual(record.title, "Media Act 2024")
        self.assertEqual(record.type, "ukpga")
        self.assertEqual(record.document_main_type, "UnitedKingdomPublicGeneralAct")
        self.assertEqual(record.year, 2024)
        self.assertEqual(record.number, 15)
        self.assertEqual(record.status, "revised")
        self.assertEqual(record.uri, "http://www.legislation.gov.uk/id/ukpga/2024/15")
        self.assertEqual(record.document_uri, "http://www.legislation.gov.uk/ukpga/2024/15")
        self.assertEqual(record.dates[0].event, "enactment")
        self.assertEqual(record.dates[0].date, "2024-05-24")
        self.assertEqual(record.pdf_url, "http://www.legislation.gov.uk/ukpga/2024/15/pdfs/ukpga_20240015_en.pdf")
        self.assertGreaterEqual(len(record.formats), 3)
        self.assertEqual(record.versions[-1].version_date, "2026-01-01")
        self.assertEqual(record.section_count, 1)
        self.assertEqual(record.part_count, 1)
        self.assertEqual(record.schedule_count, 1)
        self.assertEqual(record.statistics["TotalParagraphs"], 385)
        self.assertEqual(record.unapplied_effects_count, 1)
        self.assertEqual(record.effects[0].affected_provision, "Sch. 2 para. 12(2)")
        self.assertFalse(record.effects[0].applied)
        self.assertEqual(record.commentary[0]["id"], "key-commentary")

    def test_serialisers_are_deterministic(self) -> None:
        record = CLMLExtractor(ET.fromstring(CLML)).extract()
        first = to_json(record)
        second = to_json(record)
        self.assertEqual(first, second)
        self.assertIn('"title": "Media Act 2024"', first)
        self.assertIn("Media Act 2024", to_csv([record]))
        html = to_html(record)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<title>Legislation Summary - Media Act 2024</title>", html)
        self.assertIn("Download PDF", html)

    def test_normalise_url_handles_common_legislation_urls(self) -> None:
        self.assertEqual(
            normalise_url("https://www.legislation.gov.uk/ukpga/2024/15"),
            "https://www.legislation.gov.uk/ukpga/2024/15/data.xml",
        )
        self.assertEqual(
            normalise_url("https://www.legislation.gov.uk/id/ukpga/2024/15"),
            "https://www.legislation.gov.uk/ukpga/2024/15/data.xml",
        )
        self.assertEqual(
            normalise_url("https://www.legislation.gov.uk/uksi/2024/858/made/data.xml"),
            "https://www.legislation.gov.uk/uksi/2024/858/made/data.xml",
        )
        self.assertEqual(
            normalise_url("https://www.legislation.gov.uk/ukpga/2024/15", resources_only=True),
            "https://www.legislation.gov.uk/ukpga/2024/15/resources/data.xml",
        )


if __name__ == "__main__":
    unittest.main()
