from lxml import etree

xml = '''
<flights>
    <flight>
        <game_id>155</game_id>
        <flight_number>AV173</flight_number>
        <distance_nm>4953</distance_nm>
        <base_airport_iata>DUB</base_airport_iata>
        <dest_airport_iata>BNE</dest_airport_iata>
        <fleet_type_id>29</fleet_type_id>
        <outbound_length>23:35</outbound_length>
        <inbound_length>24:45</inbound_length>
        <turnaround_length>02:15</turnaround_length>
        <outbound_dep_time>08:00</outbound_dep_time>
        <outbound_arr_time>17:35</outbound_arr_time>
        <inbound_dep_time>19:50</inbound_dep_time>
        <inbound_arr_time>10:35</inbound_arr_time>
        <days_flown>[1]</days_flown>
        <sectors>
            <flight_sector>
                <direction>out</direction>
                <start_airport_iata>DUB</start_airport_iata>
                <end_airport_iata>MWX</end_airport_iata>
                <sector_length>12:00</sector_length>
            </flight_sector>
            <flight_sector>
                <direction>out</direction>
                <start_airport_iata>MWX</start_airport_iata>
                <end_airport_iata>BNE</end_airport_iata>
                <sector_length>10:15</sector_length>
            </flight_sector>
            <flight_sector>
                <direction>in</direction>
                <start_airport_iata>BNE</start_airport_iata>
                <end_airport_iata>MWX</end_airport_iata>
                <sector_length>10:20</sector_length>
            </flight_sector>
            <flight_sector>
                <direction>in</direction>
                <start_airport_iata>MWX</start_airport_iata>
                <end_airport_iata>DUB</end_airport_iata>
                <sector_length>13:05</sector_length>
            </flight_sector>
        </sectors>
    </flight>
<flight>
    <game_id>155</game_id>
    <flight_number>AV001</flight_number>
    <distance_nm>788</distance_nm>
    <base_airport_iata>CIA</base_airport_iata>
    <dest_airport_iata>STN</dest_airport_iata>
    <fleet_type_id>23</fleet_type_id>
    <outbound_length>02:40</outbound_length>
    <inbound_length>02:35</inbound_length>
    <turnaround_length>01:10</turnaround_length>
    <outbound_dep_time>13:20</outbound_dep_time>
    <outbound_arr_time>15:00</outbound_arr_time>
    <inbound_dep_time>16:10</inbound_dep_time>
    <inbound_arr_time>19:45</inbound_arr_time>
    <days_flown>[2]</days_flown>
<sectors></sectors>
</flight>
</flights>'''


xslt_root = '''
<xsl:stylesheet version="2.0"
xmlns:fn="http://www.w3.org/2005/xpath-functions"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:template match="/">
<html>

<head>
<title>AWS</title>
<style>
.simple {
    font-family: Courier, monospace, sans-serif;
    border-collapse: collapse;
}

caption {
    display: table-caption;
    text-align: center;
	font-size: 1.5em;
	font-weight: bold;
	font-variant: small-caps;
}

td {
    font-size: 1em;
    border: 1px solid #00007A;
    text-align: center;
    padding: 3px 6px;
}

th {
    font-size: 1.1em;
    text-align: center;
    padding: 3px 6px 2px 6px;
    border: 1px solid #ffffff;
    background-color: #404056;
    color: #ffffff;
}
</style>
</head>
  <body>
    <h2>AWS</h2>
    <table class="simple">
    <thead>
      <tr bgcolor="#eeeeee">
      <xsl:for-each select="flights/flight[1]/*">
      <xsl:variable name="colname"><xsl:value-of select="local-name()" /></xsl:variable>
      <th><xsl:value-of select="replace($colname, '_', '')"/></th>
      </xsl:for-each>
      </tr>
    </thead>

    <tbody>
      <xsl:for-each select="flights/*">
      <tr> 
          <td><xsl:value-of select="game_id"/></td>
          <td><xsl:value-of select="flight_number"/></td>
          <td><xsl:value-of select="distance_nm"/></td>
          <td><xsl:value-of select="base_airport_iata"/></td>
          <td><xsl:value-of select="dest_airport_iata"/></td>
          <td><xsl:value-of select="fleet_type_id"/></td>
          <td><xsl:value-of select="outbound_length"/></td>
          <td><xsl:value-of select="inbound_length"/></td>
          <td><xsl:value-of select="turnaround_length"/></td>
          <td><xsl:value-of select="outbound_dep_time"/></td>
          <td><xsl:value-of select="outbound_arr_time"/></td>
          <td><xsl:value-of select="inbound_dep_time"/></td>
          <td><xsl:value-of select="inbound_arr_time"/></td>
          <td><xsl:value-of select="days_flown"/></td>
          <td>
	<xsl:choose>
        <xsl:when test="sectors/flight_sector">
          <table border="1">
          <thead>
              <tr>
              <xsl:for-each select="sectors/flight_sector[1]/*">
              <th><xsl:value-of select="local-name()"/></th>
              </xsl:for-each>
              </tr>
          </thead>

          <tbody>
              <xsl:for-each select="sectors/*">
              <tr>
              <td><xsl:value-of select="direction"/></td>
              <td><xsl:value-of select="start_airport_iata"/></td>
              <td><xsl:value-of select="end_airport_iata"/></td>
              <td><xsl:value-of select="sector_length"/></td>
              </tr>
              </xsl:for-each>
          </tbody>

          </table>
	</xsl:when>

	<xsl:otherwise>
	<xsl:string>&amp;nbsp;</xsl:string>
	</xsl:otherwise>
	</xsl:choose>


          </td>
      </tr>
      </xsl:for-each>
    </tbody>
    </table>
  </body>
  </html>
</xsl:template>
</xsl:stylesheet>
'''

doc = etree.XML(xml)
print(str(doc))

transform = etree.XSLT(etree.XML(xslt_root))
print(transform)


result_tree = transform(doc)
print(str(result_tree))
