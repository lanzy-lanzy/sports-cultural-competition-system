/*M!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.20-12.3.3-MariaDB, for Win64 (AMD64)
--
-- Host: 127.0.0.1    Database: competition_hub
-- ------------------------------------------------------
-- Server version	12.3.3-MariaDB

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*M!100616 SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0 */;

--
-- Current Database: `competition_hub`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `competition_hub` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci */;

USE `competition_hub`;

--
-- Table structure for table `accounts_userprofile`
--

DROP TABLE IF EXISTS `accounts_userprofile`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_userprofile` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `role` varchar(30) NOT NULL,
  `phone` varchar(30) NOT NULL,
  `profile_image` varchar(100) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `user_id` int(11) NOT NULL,
  `middle_name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `accounts_userprofile_user_id_92240672_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_userprofile`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `accounts_userprofile` WRITE;
/*!40000 ALTER TABLE `accounts_userprofile` DISABLE KEYS */;
INSERT INTO `accounts_userprofile` VALUES
(1,'ADMINISTRATOR','','','2026-11-06 09:40:01.635004','2026-11-06 09:40:01.635024',1,''),
(2,'PARTICIPANT','09121406735','','2026-11-06 09:49:42.289917','2026-11-06 09:49:42.291948',2,'Decierdo'),
(3,'PARTICIPANT','09074557451','','2026-11-06 09:53:18.150335','2026-11-06 09:53:18.152361',3,''),
(4,'JUDGE','09098765656','','2026-11-06 09:58:06.616315','2026-11-06 09:58:06.618962',4,''),
(5,'JUDGE','09121406735','','2026-11-06 09:59:12.828567','2026-11-06 09:59:12.838642',5,'Yunting');
/*!40000 ALTER TABLE `accounts_userprofile` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `announcements_announcement`
--

DROP TABLE IF EXISTS `announcements_announcement`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `announcements_announcement` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `title` varchar(200) NOT NULL,
  `body` longtext NOT NULL,
  `audience` varchar(20) NOT NULL,
  `is_published` tinyint(1) NOT NULL,
  `published_at` datetime(6) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `competition_id` bigint(20) DEFAULT NULL,
  `created_by_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `announcements_announ_competition_id_97e809ac_fk_competiti` (`competition_id`),
  KEY `announcements_announ_created_by_id_79d7d337_fk_auth_user` (`created_by_id`),
  CONSTRAINT `announcements_announ_competition_id_97e809ac_fk_competiti` FOREIGN KEY (`competition_id`) REFERENCES `competition_app_competition` (`id`),
  CONSTRAINT `announcements_announ_created_by_id_79d7d337_fk_auth_user` FOREIGN KEY (`created_by_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `announcements_announcement`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `announcements_announcement` WRITE;
/*!40000 ALTER TABLE `announcements_announcement` DISABLE KEYS */;
/*!40000 ALTER TABLE `announcements_announcement` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `announcements_notification`
--

DROP TABLE IF EXISTS `announcements_notification`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `announcements_notification` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `title` varchar(200) NOT NULL,
  `body` longtext NOT NULL,
  `link` varchar(300) NOT NULL,
  `is_read` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `recipient_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `announcements_notification_recipient_id_0ba870c3_fk_auth_user_id` (`recipient_id`),
  CONSTRAINT `announcements_notification_recipient_id_0ba870c3_fk_auth_user_id` FOREIGN KEY (`recipient_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `announcements_notification`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `announcements_notification` WRITE;
/*!40000 ALTER TABLE `announcements_notification` DISABLE KEYS */;
INSERT INTO `announcements_notification` VALUES
(1,'Registration approved','Your registration for LATIN AMERICAN DANCE SPORT has been approved.','',0,'2026-11-06 09:56:15.868273',2),
(2,'Registration approved','Your registration for LATIN AMERICAN DANCE SPORT has been approved.','',0,'2026-11-06 09:56:22.398750',3);
/*!40000 ALTER TABLE `announcements_notification` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `announcements_notificationpreference`
--

DROP TABLE IF EXISTS `announcements_notificationpreference`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `announcements_notificationpreference` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `email_enabled` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `user_id` int(11) NOT NULL,
  `sms_enabled` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `announcements_notifi_user_id_9064f447_fk_auth_user` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `announcements_notificationpreference`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `announcements_notificationpreference` WRITE;
/*!40000 ALTER TABLE `announcements_notificationpreference` DISABLE KEYS */;
INSERT INTO `announcements_notificationpreference` VALUES
(1,1,'2026-11-06 09:56:15.871338','2026-11-06 09:56:15.871358',2,1),
(2,1,'2026-11-06 09:56:22.403092','2026-11-06 09:56:22.403137',3,1);
/*!40000 ALTER TABLE `announcements_notificationpreference` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `auth_group`
--

DROP TABLE IF EXISTS `auth_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `auth_group` WRITE;
/*!40000 ALTER TABLE `auth_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `auth_group_permissions`
--

DROP TABLE IF EXISTS `auth_group_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group_permissions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `group_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group_permissions`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `auth_group_permissions` WRITE;
/*!40000 ALTER TABLE `auth_group_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group_permissions` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `auth_permission`
--

DROP TABLE IF EXISTS `auth_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_permission` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `content_type_id` int(11) NOT NULL,
  `codename` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=149 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_permission`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `auth_permission` WRITE;
/*!40000 ALTER TABLE `auth_permission` DISABLE KEYS */;
INSERT INTO `auth_permission` VALUES
(1,'Can add log entry',1,'add_logentry'),
(2,'Can change log entry',1,'change_logentry'),
(3,'Can delete log entry',1,'delete_logentry'),
(4,'Can view log entry',1,'view_logentry'),
(5,'Can add permission',3,'add_permission'),
(6,'Can change permission',3,'change_permission'),
(7,'Can delete permission',3,'delete_permission'),
(8,'Can view permission',3,'view_permission'),
(9,'Can add group',2,'add_group'),
(10,'Can change group',2,'change_group'),
(11,'Can delete group',2,'delete_group'),
(12,'Can view group',2,'view_group'),
(13,'Can add user',4,'add_user'),
(14,'Can change user',4,'change_user'),
(15,'Can delete user',4,'delete_user'),
(16,'Can view user',4,'view_user'),
(17,'Can add content type',5,'add_contenttype'),
(18,'Can change content type',5,'change_contenttype'),
(19,'Can delete content type',5,'delete_contenttype'),
(20,'Can view content type',5,'view_contenttype'),
(21,'Can add session',6,'add_session'),
(22,'Can change session',6,'change_session'),
(23,'Can delete session',6,'delete_session'),
(24,'Can view session',6,'view_session'),
(25,'Can add user profile',7,'add_userprofile'),
(26,'Can change user profile',7,'change_userprofile'),
(27,'Can delete user profile',7,'delete_userprofile'),
(28,'Can view user profile',7,'view_userprofile'),
(29,'Can add competition',8,'add_competition'),
(30,'Can change competition',8,'change_competition'),
(31,'Can delete competition',8,'delete_competition'),
(32,'Can view competition',8,'view_competition'),
(33,'Can add round',10,'add_round'),
(34,'Can change round',10,'change_round'),
(35,'Can delete round',10,'delete_round'),
(36,'Can view round',10,'view_round'),
(37,'Can add criterion',9,'add_criterion'),
(38,'Can change criterion',9,'change_criterion'),
(39,'Can delete criterion',9,'delete_criterion'),
(40,'Can view criterion',9,'view_criterion'),
(41,'Can add participant',11,'add_participant'),
(42,'Can change participant',11,'change_participant'),
(43,'Can delete participant',11,'delete_participant'),
(44,'Can view participant',11,'view_participant'),
(45,'Can add participant competition',12,'add_participantcompetition'),
(46,'Can change participant competition',12,'change_participantcompetition'),
(47,'Can delete participant competition',12,'delete_participantcompetition'),
(48,'Can view participant competition',12,'view_participantcompetition'),
(49,'Can add team',13,'add_team'),
(50,'Can change team',13,'change_team'),
(51,'Can delete team',13,'delete_team'),
(52,'Can view team',13,'view_team'),
(53,'Can add team staff',15,'add_teamstaff'),
(54,'Can change team staff',15,'change_teamstaff'),
(55,'Can delete team staff',15,'delete_teamstaff'),
(56,'Can view team staff',15,'view_teamstaff'),
(57,'Can add team membership',14,'add_teammembership'),
(58,'Can change team membership',14,'change_teammembership'),
(59,'Can delete team membership',14,'delete_teammembership'),
(60,'Can view team membership',14,'view_teammembership'),
(61,'Can add judge',16,'add_judge'),
(62,'Can change judge',16,'change_judge'),
(63,'Can delete judge',16,'delete_judge'),
(64,'Can view judge',16,'view_judge'),
(65,'Can add judge assignment',17,'add_judgeassignment'),
(66,'Can change judge assignment',17,'change_judgeassignment'),
(67,'Can delete judge assignment',17,'delete_judgeassignment'),
(68,'Can view judge assignment',17,'view_judgeassignment'),
(69,'Can add score',21,'add_score'),
(70,'Can change score',21,'change_score'),
(71,'Can delete score',21,'delete_score'),
(72,'Can view score',21,'view_score'),
(73,'Can add score change log',22,'add_scorechangelog'),
(74,'Can change score change log',22,'change_scorechangelog'),
(75,'Can delete score change log',22,'delete_scorechangelog'),
(76,'Can view score change log',22,'view_scorechangelog'),
(77,'Can add competition result',20,'add_competitionresult'),
(78,'Can change competition result',20,'change_competitionresult'),
(79,'Can delete competition result',20,'delete_competitionresult'),
(80,'Can view competition result',20,'view_competitionresult'),
(81,'Can add award',18,'add_award'),
(82,'Can change award',18,'change_award'),
(83,'Can delete award',18,'delete_award'),
(84,'Can view award',18,'view_award'),
(85,'Can add award recipient',19,'add_awardrecipient'),
(86,'Can change award recipient',19,'change_awardrecipient'),
(87,'Can delete award recipient',19,'delete_awardrecipient'),
(88,'Can view award recipient',19,'view_awardrecipient'),
(89,'Can add sport type',27,'add_sporttype'),
(90,'Can change sport type',27,'change_sporttype'),
(91,'Can delete sport type',27,'delete_sporttype'),
(92,'Can view sport type',27,'view_sporttype'),
(93,'Can add venue',28,'add_venue'),
(94,'Can change venue',28,'change_venue'),
(95,'Can delete venue',28,'delete_venue'),
(96,'Can view venue',28,'view_venue'),
(97,'Can add sports event',26,'add_sportsevent'),
(98,'Can change sports event',26,'change_sportsevent'),
(99,'Can delete sports event',26,'delete_sportsevent'),
(100,'Can view sports event',26,'view_sportsevent'),
(101,'Can add event entry',23,'add_evententry'),
(102,'Can change event entry',23,'change_evententry'),
(103,'Can delete event entry',23,'delete_evententry'),
(104,'Can view event entry',23,'view_evententry'),
(105,'Can add match',24,'add_match'),
(106,'Can change match',24,'change_match'),
(107,'Can delete match',24,'delete_match'),
(108,'Can view match',24,'view_match'),
(109,'Can add match entry',25,'add_matchentry'),
(110,'Can change match entry',25,'change_matchentry'),
(111,'Can delete match entry',25,'delete_matchentry'),
(112,'Can view match entry',25,'view_matchentry'),
(113,'Can add eligibility record',29,'add_eligibilityrecord'),
(114,'Can change eligibility record',29,'change_eligibilityrecord'),
(115,'Can delete eligibility record',29,'delete_eligibilityrecord'),
(116,'Can view eligibility record',29,'view_eligibilityrecord'),
(117,'Can add announcement',30,'add_announcement'),
(118,'Can change announcement',30,'change_announcement'),
(119,'Can delete announcement',30,'delete_announcement'),
(120,'Can view announcement',30,'view_announcement'),
(121,'Can add notification',31,'add_notification'),
(122,'Can change notification',31,'change_notification'),
(123,'Can delete notification',31,'delete_notification'),
(124,'Can view notification',31,'view_notification'),
(125,'Can add notification preference',32,'add_notificationpreference'),
(126,'Can change notification preference',32,'change_notificationpreference'),
(127,'Can delete notification preference',32,'delete_notificationpreference'),
(128,'Can view notification preference',32,'view_notificationpreference'),
(129,'Can add event registration',33,'add_eventregistration'),
(130,'Can change event registration',33,'change_eventregistration'),
(131,'Can delete event registration',33,'delete_eventregistration'),
(132,'Can view event registration',33,'view_eventregistration'),
(133,'Can add registration template',34,'add_registrationtemplate'),
(134,'Can change registration template',34,'change_registrationtemplate'),
(135,'Can delete registration template',34,'delete_registrationtemplate'),
(136,'Can view registration template',34,'view_registrationtemplate'),
(137,'Can add protest',35,'add_protest'),
(138,'Can change protest',35,'change_protest'),
(139,'Can delete protest',35,'delete_protest'),
(140,'Can view protest',35,'view_protest'),
(141,'Can add audit log',36,'add_auditlog'),
(142,'Can change audit log',36,'change_auditlog'),
(143,'Can delete audit log',36,'delete_auditlog'),
(144,'Can view audit log',36,'view_auditlog'),
(145,'Can add sms message',37,'add_smsmessage'),
(146,'Can change sms message',37,'change_smsmessage'),
(147,'Can delete sms message',37,'delete_smsmessage'),
(148,'Can view sms message',37,'view_smsmessage');
/*!40000 ALTER TABLE `auth_permission` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `auth_user`
--

DROP TABLE IF EXISTS `auth_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `auth_user` WRITE;
/*!40000 ALTER TABLE `auth_user` DISABLE KEYS */;
INSERT INTO `auth_user` VALUES
(1,'pbkdf2_sha256$1200000$Gs8YaJ9No1ArLuDE7n6ARh$7WMUoXW8y+wcc+hmtOw7YYhXkjI1ZAYUUfOIRgMjkjQ=','2026-11-09 03:15:37.792931',1,'admin','Andrea','Dela Fuente','andrea.delafuente@gmail.com',1,1,'2026-10-15 02:30:52.723591'),
(2,'pbkdf2_sha256$1200000$6pJCSlIjquEQJ1QTBYFCH8$00kXDtJ1F/lj5yrW77DrTvWRYg2QxWuBpOSGJWw0Uaw=','2026-11-06 09:50:36.601743',0,'Rine@gmail.com','Irine','Bagting','',0,1,'2026-11-06 09:49:41.159638'),
(3,'pbkdf2_sha256$1200000$WO9rd2YuXuUFXKvqHDN6XN$sCdPBqQWrAx2sG3mMWJfjg470m0+O015empSMBvQ7y0=','2026-11-06 09:53:42.185386',0,'rhoffamie','Rhoffa Mie','Biadog','',0,1,'2026-11-06 09:53:17.048652'),
(4,'pbkdf2_sha256$1200000$SRXOgb5CwiUsiXTrSXDxqs$Zgr0wA2QzX1Wirt+VHm9G+YBleOem3a6MEeiz8rl6cw=','2026-11-06 09:58:23.819492',0,'mhycoo','Mhyco','Delgado','',0,1,'2026-11-06 09:58:05.722721'),
(5,'pbkdf2_sha256$1200000$h90a382xUjK8eu9KxupUI0$Sh9LTtXN0Fy1TVx3xQPU1CcSJLQ1LAKkdX9ooiW7Bcc=','2026-11-06 09:59:53.580946',0,'indayai121303','Cherry','Boss','',0,1,'2026-11-06 09:59:11.744586');
/*!40000 ALTER TABLE `auth_user` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `auth_user_groups`
--

DROP TABLE IF EXISTS `auth_user_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user_groups` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `group_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_groups_user_id_group_id_94350c0c_uniq` (`user_id`,`group_id`),
  KEY `auth_user_groups_group_id_97559544_fk_auth_group_id` (`group_id`),
  CONSTRAINT `auth_user_groups_group_id_97559544_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `auth_user_groups_user_id_6a12ed8b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user_groups`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `auth_user_groups` WRITE;
/*!40000 ALTER TABLE `auth_user_groups` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_groups` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `auth_user_user_permissions`
--

DROP TABLE IF EXISTS `auth_user_user_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user_user_permissions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_user_permissions_user_id_permission_id_14a6b632_uniq` (`user_id`,`permission_id`),
  KEY `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user_user_permissions`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `auth_user_user_permissions` WRITE;
/*!40000 ALTER TABLE `auth_user_user_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_user_permissions` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_auditlog`
--

DROP TABLE IF EXISTS `competition_app_auditlog`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_auditlog` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `action` varchar(50) NOT NULL,
  `object_id` bigint(20) unsigned DEFAULT NULL CHECK (`object_id` >= 0),
  `details` longtext NOT NULL,
  `ip_address` char(39) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `content_type_id` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `competition_app_audi_content_type_id_4d1fe546_fk_django_co` (`content_type_id`),
  KEY `competition_action_dc5555_idx` (`action`),
  KEY `competition_user_id_3986f4_idx` (`user_id`),
  KEY `competition_created_a2858a_idx` (`created_at`),
  CONSTRAINT `competition_app_audi_content_type_id_4d1fe546_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `competition_app_auditlog_user_id_65d3cc6a_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_auditlog`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_auditlog` WRITE;
/*!40000 ALTER TABLE `competition_app_auditlog` DISABLE KEYS */;
INSERT INTO `competition_app_auditlog` VALUES
(1,'TEAM_STATUS',2,'Team \"Team Blue\" status changed to Approved','192.168.100.98','2026-11-06 09:49:05.686807',13,1),
(2,'TEAM_STATUS',1,'Team \"Team Red\" status changed to Approved','192.168.100.98','2026-11-06 09:49:19.635211',13,1),
(3,'TEAM_MEMBERSHIP',2,'Irine Decierdo Bagting selected team \"Team Blue\"','192.168.100.223','2026-11-06 09:53:20.264804',13,2),
(4,'TEAM_MEMBERSHIP',1,'Rhoffa Mie Biadog selected team \"Team Red\"','192.168.100.181','2026-11-06 09:54:52.372631',13,3),
(5,'REGISTRATION_REVIEW',1,'Registration approved for Irine Decierdo Bagting','192.168.100.98','2026-11-06 09:56:15.875190',33,1),
(6,'REGISTRATION_REVIEW',2,'Registration approved for Rhoffa Mie Biadog','192.168.100.98','2026-11-06 09:56:22.407387',33,1),
(7,'SCORE_SUBMIT',1,'Scores submitted for Irine Decierdo Bagting in LATIN AMERICAN DANCE SPORT - DIRECT SCORING','192.168.100.223','2026-11-06 10:01:16.063620',11,5),
(8,'SCORE_SUBMIT',2,'Scores submitted for Rhoffa Mie Biadog in LATIN AMERICAN DANCE SPORT - DIRECT SCORING','192.168.100.223','2026-11-06 10:01:36.478350',11,5),
(9,'SCORE_SUBMIT',2,'Scores submitted for Rhoffa Mie Biadog in LATIN AMERICAN DANCE SPORT - DIRECT SCORING','192.168.100.181','2026-11-06 10:01:47.015404',11,4);
/*!40000 ALTER TABLE `competition_app_auditlog` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_award`
--

DROP TABLE IF EXISTS `competition_app_award`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_award` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `type` varchar(20) NOT NULL,
  `description` longtext NOT NULL,
  `rank` int(10) unsigned DEFAULT NULL CHECK (`rank` >= 0),
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `competition_id` bigint(20) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `competition_app_awar_competition_id_1d22c630_fk_competiti` (`competition_id`),
  CONSTRAINT `competition_app_awar_competition_id_1d22c630_fk_competiti` FOREIGN KEY (`competition_id`) REFERENCES `competition_app_competition` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_award`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_award` WRITE;
/*!40000 ALTER TABLE `competition_app_award` DISABLE KEYS */;
/*!40000 ALTER TABLE `competition_app_award` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_awardrecipient`
--

DROP TABLE IF EXISTS `competition_app_awardrecipient`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_awardrecipient` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `recipient_type` varchar(20) NOT NULL,
  `citation` longtext NOT NULL,
  `awarded_at` datetime(6) NOT NULL,
  `award_id` bigint(20) NOT NULL,
  `participant_id` bigint(20) DEFAULT NULL,
  `team_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_award_participant` (`award_id`,`participant_id`),
  UNIQUE KEY `unique_award_team` (`award_id`,`team_id`),
  KEY `competition_app_awar_participant_id_1bc6cf8d_fk_competiti` (`participant_id`),
  KEY `competition_app_awardrecipient_team_id_6a18ebc0_fk_teams_team_id` (`team_id`),
  CONSTRAINT `competition_app_awar_award_id_cf4e5d12_fk_competiti` FOREIGN KEY (`award_id`) REFERENCES `competition_app_award` (`id`),
  CONSTRAINT `competition_app_awar_participant_id_1bc6cf8d_fk_competiti` FOREIGN KEY (`participant_id`) REFERENCES `competition_app_participant` (`id`),
  CONSTRAINT `competition_app_awardrecipient_team_id_6a18ebc0_fk_teams_team_id` FOREIGN KEY (`team_id`) REFERENCES `teams_team` (`id`),
  CONSTRAINT `award_recipient_single_contestant` CHECK (`participant_id` is not null and `team_id` is null or `participant_id` is null and `team_id` is not null)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_awardrecipient`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_awardrecipient` WRITE;
/*!40000 ALTER TABLE `competition_app_awardrecipient` DISABLE KEYS */;
/*!40000 ALTER TABLE `competition_app_awardrecipient` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_competition`
--

DROP TABLE IF EXISTS `competition_app_competition`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_competition` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `description` longtext NOT NULL,
  `start_date` datetime(6) NOT NULL,
  `end_date` datetime(6) NOT NULL,
  `status` varchar(20) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `show_results` tinyint(1) NOT NULL,
  `created_by_id` int(11) NOT NULL,
  `bronze_points` decimal(5,2) NOT NULL,
  `cultural_event_type` varchar(30) NOT NULL,
  `gold_points` decimal(5,2) NOT NULL,
  `kind` varchar(20) NOT NULL,
  `silver_points` decimal(5,2) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `competition_app_comp_created_by_id_529c347e_fk_auth_user` (`created_by_id`),
  CONSTRAINT `competition_app_comp_created_by_id_529c347e_fk_auth_user` FOREIGN KEY (`created_by_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_competition`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_competition` WRITE;
/*!40000 ALTER TABLE `competition_app_competition` DISABLE KEYS */;
INSERT INTO `competition_app_competition` VALUES
(1,'LATIN AMERICAN DANCE SPORT','','2026-11-06 00:00:00.000000','2026-11-14 00:00:00.000000','ACTIVE','2026-11-06 09:52:55.488261','2026-11-06 09:52:55.488302',0,1,3.00,'DANCE',10.00,'CULTURAL',5.00);
/*!40000 ALTER TABLE `competition_app_competition` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_competitionresult`
--

DROP TABLE IF EXISTS `competition_app_competitionresult`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_competitionresult` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `total_score` decimal(10,2) NOT NULL,
  `rank` int(10) unsigned NOT NULL CHECK (`rank` >= 0),
  `timestamp` datetime(6) NOT NULL,
  `competition_id` bigint(20) NOT NULL,
  `participant_id` bigint(20) NOT NULL,
  `round_id` bigint(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `competition_app_competit_competition_id_participa_39c496a6_uniq` (`competition_id`,`participant_id`,`round_id`),
  KEY `competition_app_comp_participant_id_a7687b72_fk_competiti` (`participant_id`),
  KEY `competition_app_comp_round_id_7ac3736d_fk_competiti` (`round_id`),
  CONSTRAINT `competition_app_comp_competition_id_49668966_fk_competiti` FOREIGN KEY (`competition_id`) REFERENCES `competition_app_competition` (`id`),
  CONSTRAINT `competition_app_comp_participant_id_a7687b72_fk_competiti` FOREIGN KEY (`participant_id`) REFERENCES `competition_app_participant` (`id`),
  CONSTRAINT `competition_app_comp_round_id_7ac3736d_fk_competiti` FOREIGN KEY (`round_id`) REFERENCES `competition_app_round` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_competitionresult`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_competitionresult` WRITE;
/*!40000 ALTER TABLE `competition_app_competitionresult` DISABLE KEYS */;
INSERT INTO `competition_app_competitionresult` VALUES
(1,89.80,2,'2026-11-07 11:33:49.304812',1,1,1),
(2,93.20,1,'2026-11-07 11:33:49.300914',1,2,1);
/*!40000 ALTER TABLE `competition_app_competitionresult` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_criterion`
--

DROP TABLE IF EXISTS `competition_app_criterion`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_criterion` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `description` longtext NOT NULL,
  `max_score` decimal(5,2) NOT NULL,
  `round_id` bigint(20) NOT NULL,
  `weight_percentage` decimal(5,2) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `competition_app_crit_round_id_051665d9_fk_competiti` (`round_id`),
  CONSTRAINT `competition_app_crit_round_id_051665d9_fk_competiti` FOREIGN KEY (`round_id`) REFERENCES `competition_app_round` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_criterion`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_criterion` WRITE;
/*!40000 ALTER TABLE `competition_app_criterion` DISABLE KEYS */;
INSERT INTO `competition_app_criterion` VALUES
(1,'CHA CHA CHA','FACIAL EXPRESSION AND TIMING',30.00,1,0.00),
(2,'RUMBA','LOVE DANCE',40.00,1,0.00),
(3,'JIVE','AGILITY',30.00,1,0.00);
/*!40000 ALTER TABLE `competition_app_criterion` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_evententry`
--

DROP TABLE IF EXISTS `competition_app_evententry`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_evententry` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `seed` int(10) unsigned DEFAULT NULL CHECK (`seed` >= 0),
  `status` varchar(20) NOT NULL,
  `registered_at` datetime(6) NOT NULL,
  `participant_id` bigint(20) DEFAULT NULL,
  `team_id` bigint(20) DEFAULT NULL,
  `event_id` bigint(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_event_team_entry` (`event_id`,`team_id`),
  UNIQUE KEY `unique_event_participant_entry` (`event_id`,`participant_id`),
  KEY `competition_app_even_participant_id_6e566f22_fk_competiti` (`participant_id`),
  KEY `competition_app_evententry_team_id_4c8ed6ec_fk_teams_team_id` (`team_id`),
  CONSTRAINT `competition_app_even_event_id_b581ee04_fk_competiti` FOREIGN KEY (`event_id`) REFERENCES `competition_app_sportsevent` (`id`),
  CONSTRAINT `competition_app_even_participant_id_6e566f22_fk_competiti` FOREIGN KEY (`participant_id`) REFERENCES `competition_app_participant` (`id`),
  CONSTRAINT `competition_app_evententry_team_id_4c8ed6ec_fk_teams_team_id` FOREIGN KEY (`team_id`) REFERENCES `teams_team` (`id`),
  CONSTRAINT `event_entry_single_contestant` CHECK (`team_id` is not null and `participant_id` is null or `team_id` is null and `participant_id` is not null)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_evententry`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_evententry` WRITE;
/*!40000 ALTER TABLE `competition_app_evententry` DISABLE KEYS */;
/*!40000 ALTER TABLE `competition_app_evententry` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_judge`
--

DROP TABLE IF EXISTS `competition_app_judge`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_judge` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `phone` varchar(20) NOT NULL,
  `profile_image` varchar(100) DEFAULT NULL,
  `expertise` varchar(200) NOT NULL,
  `bio` longtext NOT NULL,
  `status` varchar(20) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `competition_app_judge_user_id_477114e0_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_judge`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_judge` WRITE;
/*!40000 ALTER TABLE `competition_app_judge` DISABLE KEYS */;
INSERT INTO `competition_app_judge` VALUES
(1,'09098765656','defaults/people.svg','','','ACTIVE','2026-11-06 09:58:06.621880',4),
(2,'09121406735','defaults/people.svg','','','ACTIVE','2026-11-06 09:59:12.842864',5);
/*!40000 ALTER TABLE `competition_app_judge` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_judgeassignment`
--

DROP TABLE IF EXISTS `competition_app_judgeassignment`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_judgeassignment` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `assigned_at` datetime(6) NOT NULL,
  `status` varchar(20) NOT NULL,
  `competition_id` bigint(20) NOT NULL,
  `judge_id` bigint(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `competition_app_judgeass_judge_id_competition_id_3e9da6fe_uniq` (`judge_id`,`competition_id`),
  KEY `competition_app_judg_competition_id_f76144f3_fk_competiti` (`competition_id`),
  CONSTRAINT `competition_app_judg_competition_id_f76144f3_fk_competiti` FOREIGN KEY (`competition_id`) REFERENCES `competition_app_competition` (`id`),
  CONSTRAINT `competition_app_judg_judge_id_5bbdc9f5_fk_competiti` FOREIGN KEY (`judge_id`) REFERENCES `competition_app_judge` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_judgeassignment`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_judgeassignment` WRITE;
/*!40000 ALTER TABLE `competition_app_judgeassignment` DISABLE KEYS */;
INSERT INTO `competition_app_judgeassignment` VALUES
(1,'2026-11-06 10:00:21.720205','ACTIVE',1,1),
(2,'2026-11-06 10:00:21.735686','ACTIVE',1,2);
/*!40000 ALTER TABLE `competition_app_judgeassignment` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_judgeassignment_rounds`
--

DROP TABLE IF EXISTS `competition_app_judgeassignment_rounds`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_judgeassignment_rounds` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `judgeassignment_id` bigint(20) NOT NULL,
  `round_id` bigint(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `competition_app_judgeass_judgeassignment_id_round_9ee645a3_uniq` (`judgeassignment_id`,`round_id`),
  KEY `competition_app_judg_round_id_c078a575_fk_competiti` (`round_id`),
  CONSTRAINT `competition_app_judg_judgeassignment_id_ffc00aaa_fk_competiti` FOREIGN KEY (`judgeassignment_id`) REFERENCES `competition_app_judgeassignment` (`id`),
  CONSTRAINT `competition_app_judg_round_id_c078a575_fk_competiti` FOREIGN KEY (`round_id`) REFERENCES `competition_app_round` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_judgeassignment_rounds`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_judgeassignment_rounds` WRITE;
/*!40000 ALTER TABLE `competition_app_judgeassignment_rounds` DISABLE KEYS */;
INSERT INTO `competition_app_judgeassignment_rounds` VALUES
(1,1,1),
(2,2,1);
/*!40000 ALTER TABLE `competition_app_judgeassignment_rounds` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_match`
--

DROP TABLE IF EXISTS `competition_app_match`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_match` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  `round_number` int(10) unsigned NOT NULL CHECK (`round_number` >= 0),
  `scheduled_start` datetime(6) DEFAULT NULL,
  `scheduled_end` datetime(6) DEFAULT NULL,
  `status` varchar(20) NOT NULL,
  `notes` longtext NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `next_match_id` bigint(20) DEFAULT NULL,
  `event_id` bigint(20) NOT NULL,
  `venue_id` bigint(20) DEFAULT NULL,
  `group` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `competition_app_matc_next_match_id_a6108dc7_fk_competiti` (`next_match_id`),
  KEY `competition_app_matc_event_id_8ab8fd5e_fk_competiti` (`event_id`),
  KEY `competition_app_matc_venue_id_00016a77_fk_competiti` (`venue_id`),
  CONSTRAINT `competition_app_matc_event_id_8ab8fd5e_fk_competiti` FOREIGN KEY (`event_id`) REFERENCES `competition_app_sportsevent` (`id`),
  CONSTRAINT `competition_app_matc_next_match_id_a6108dc7_fk_competiti` FOREIGN KEY (`next_match_id`) REFERENCES `competition_app_match` (`id`),
  CONSTRAINT `competition_app_matc_venue_id_00016a77_fk_competiti` FOREIGN KEY (`venue_id`) REFERENCES `competition_app_venue` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_match`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_match` WRITE;
/*!40000 ALTER TABLE `competition_app_match` DISABLE KEYS */;
/*!40000 ALTER TABLE `competition_app_match` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_matchentry`
--

DROP TABLE IF EXISTS `competition_app_matchentry`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_matchentry` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `side` int(10) unsigned NOT NULL CHECK (`side` >= 0),
  `score` decimal(6,2) DEFAULT NULL,
  `is_winner` tinyint(1) NOT NULL,
  `is_draw` tinyint(1) NOT NULL,
  `match_id` bigint(20) NOT NULL,
  `participant_id` bigint(20) DEFAULT NULL,
  `team_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_match_side` (`match_id`,`side`),
  KEY `competition_app_matc_participant_id_e4b8b882_fk_competiti` (`participant_id`),
  KEY `competition_app_matchentry_team_id_62d5419e_fk_teams_team_id` (`team_id`),
  CONSTRAINT `competition_app_matc_match_id_4a53a688_fk_competiti` FOREIGN KEY (`match_id`) REFERENCES `competition_app_match` (`id`),
  CONSTRAINT `competition_app_matc_participant_id_e4b8b882_fk_competiti` FOREIGN KEY (`participant_id`) REFERENCES `competition_app_participant` (`id`),
  CONSTRAINT `competition_app_matchentry_team_id_62d5419e_fk_teams_team_id` FOREIGN KEY (`team_id`) REFERENCES `teams_team` (`id`),
  CONSTRAINT `match_entry_single_contestant` CHECK (`team_id` is not null and `participant_id` is null or `team_id` is null and `participant_id` is not null)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_matchentry`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_matchentry` WRITE;
/*!40000 ALTER TABLE `competition_app_matchentry` DISABLE KEYS */;
/*!40000 ALTER TABLE `competition_app_matchentry` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_participant`
--

DROP TABLE IF EXISTS `competition_app_participant`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_participant` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `profile_image` varchar(100) DEFAULT NULL,
  `email` varchar(254) DEFAULT NULL,
  `phone` varchar(20) NOT NULL,
  `age` int(10) unsigned DEFAULT NULL CHECK (`age` >= 0),
  `gender` varchar(20) NOT NULL,
  `bio` longtext NOT NULL,
  `achievements` longtext NOT NULL,
  `registration_date` datetime(6) NOT NULL,
  `status` varchar(20) NOT NULL,
  `performance_metrics` longtext NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `participant_id` varchar(20) NOT NULL,
  `birth_date` date DEFAULT NULL,
  `category` varchar(20) NOT NULL,
  `team_name` varchar(150) NOT NULL,
  `identification_number` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `user_id` (`user_id`),
  UNIQUE KEY `participant_id` (`participant_id`),
  CONSTRAINT `competition_app_participant_user_id_688a8903_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_participant`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_participant` WRITE;
/*!40000 ALTER TABLE `competition_app_participant` DISABLE KEYS */;
INSERT INTO `competition_app_participant` VALUES
(1,'Irine Decierdo Bagting','participant_profiles/1063.png','Rine@gmail.com@jhcsc.edu.ph','09121406735',22,'female','','','2026-11-06 09:51:55.205290','ACTIVE','',2,'JHCSC-92EBA91335','2003-11-13','OPEN','Team Blue','45687'),
(2,'Rhoffa Mie Biadog','','rhoffamie@jhcsc.edu.ph','09074557451',26,'female','','','2026-11-06 09:54:41.133477','ACTIVE','',3,'JHCSC-D0BE2B9D81','2000-09-28','SENIOR','Team Red','888991');
/*!40000 ALTER TABLE `competition_app_participant` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_participantcompetition`
--

DROP TABLE IF EXISTS `competition_app_participantcompetition`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_participantcompetition` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `number` int(10) unsigned NOT NULL CHECK (`number` >= 0),
  `registration_date` datetime(6) NOT NULL,
  `competition_id` bigint(20) NOT NULL,
  `participant_id` bigint(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `competition_app_particip_competition_id_number_e7536dfd_uniq` (`competition_id`,`number`),
  UNIQUE KEY `unique_participant_per_competition` (`participant_id`,`competition_id`),
  CONSTRAINT `competition_app_part_competition_id_317d058f_fk_competiti` FOREIGN KEY (`competition_id`) REFERENCES `competition_app_competition` (`id`),
  CONSTRAINT `competition_app_part_participant_id_6829d8d5_fk_competiti` FOREIGN KEY (`participant_id`) REFERENCES `competition_app_participant` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_participantcompetition`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_participantcompetition` WRITE;
/*!40000 ALTER TABLE `competition_app_participantcompetition` DISABLE KEYS */;
INSERT INTO `competition_app_participantcompetition` VALUES
(1,1,'2026-11-06 09:56:15.866982',1,1),
(2,2,'2026-11-06 09:56:22.396163',1,2);
/*!40000 ALTER TABLE `competition_app_participantcompetition` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_protest`
--

DROP TABLE IF EXISTS `competition_app_protest`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_protest` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `title` varchar(200) NOT NULL,
  `description` longtext NOT NULL,
  `supporting_document` varchar(100) DEFAULT NULL,
  `status` varchar(20) NOT NULL,
  `decision` longtext NOT NULL,
  `submitted_at` datetime(6) NOT NULL,
  `reviewed_at` datetime(6) DEFAULT NULL,
  `competition_id` bigint(20) DEFAULT NULL,
  `match_id` bigint(20) DEFAULT NULL,
  `reviewed_by_id` int(11) DEFAULT NULL,
  `sport_event_id` bigint(20) DEFAULT NULL,
  `submitter_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `competition_app_prot_competition_id_fb139bc9_fk_competiti` (`competition_id`),
  KEY `competition_app_prot_match_id_9fca5464_fk_competiti` (`match_id`),
  KEY `competition_app_protest_reviewed_by_id_022a7042_fk_auth_user_id` (`reviewed_by_id`),
  KEY `competition_app_prot_sport_event_id_6925e3c7_fk_competiti` (`sport_event_id`),
  KEY `competition_app_protest_submitter_id_a33800f7_fk_auth_user_id` (`submitter_id`),
  CONSTRAINT `competition_app_prot_competition_id_fb139bc9_fk_competiti` FOREIGN KEY (`competition_id`) REFERENCES `competition_app_competition` (`id`),
  CONSTRAINT `competition_app_prot_match_id_9fca5464_fk_competiti` FOREIGN KEY (`match_id`) REFERENCES `competition_app_match` (`id`),
  CONSTRAINT `competition_app_prot_sport_event_id_6925e3c7_fk_competiti` FOREIGN KEY (`sport_event_id`) REFERENCES `competition_app_sportsevent` (`id`),
  CONSTRAINT `competition_app_protest_reviewed_by_id_022a7042_fk_auth_user_id` FOREIGN KEY (`reviewed_by_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `competition_app_protest_submitter_id_a33800f7_fk_auth_user_id` FOREIGN KEY (`submitter_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `protest_has_target` CHECK (`competition_id` is not null or `sport_event_id` is not null or `match_id` is not null)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_protest`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_protest` WRITE;
/*!40000 ALTER TABLE `competition_app_protest` DISABLE KEYS */;
/*!40000 ALTER TABLE `competition_app_protest` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_protest_reviewers`
--

DROP TABLE IF EXISTS `competition_app_protest_reviewers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_protest_reviewers` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `protest_id` bigint(20) NOT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `competition_app_protest__protest_id_user_id_a71918b4_uniq` (`protest_id`,`user_id`),
  KEY `competition_app_prot_user_id_28e4336a_fk_auth_user` (`user_id`),
  CONSTRAINT `competition_app_prot_protest_id_8b75a26a_fk_competiti` FOREIGN KEY (`protest_id`) REFERENCES `competition_app_protest` (`id`),
  CONSTRAINT `competition_app_prot_user_id_28e4336a_fk_auth_user` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_protest_reviewers`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_protest_reviewers` WRITE;
/*!40000 ALTER TABLE `competition_app_protest_reviewers` DISABLE KEYS */;
/*!40000 ALTER TABLE `competition_app_protest_reviewers` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_round`
--

DROP TABLE IF EXISTS `competition_app_round`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_round` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `description` longtext NOT NULL,
  `order` int(10) unsigned NOT NULL CHECK (`order` >= 0),
  `status` varchar(20) NOT NULL,
  `weight_percentage` decimal(5,2) NOT NULL,
  `competition_id` bigint(20) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `competition_app_roun_competition_id_f97e69c9_fk_competiti` (`competition_id`),
  CONSTRAINT `competition_app_roun_competition_id_f97e69c9_fk_competiti` FOREIGN KEY (`competition_id`) REFERENCES `competition_app_competition` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_round`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_round` WRITE;
/*!40000 ALTER TABLE `competition_app_round` DISABLE KEYS */;
INSERT INTO `competition_app_round` VALUES
(1,'DIRECT SCORING','',0,'ONGOING',100.00,1);
/*!40000 ALTER TABLE `competition_app_round` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_score`
--

DROP TABLE IF EXISTS `competition_app_score`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_score` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `score` decimal(5,2) NOT NULL,
  `remarks` longtext NOT NULL,
  `timestamp` datetime(6) NOT NULL,
  `status` varchar(20) NOT NULL,
  `criterion_id` bigint(20) NOT NULL,
  `judge_id` bigint(20) NOT NULL,
  `participant_id` bigint(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `competition_app_score_participant_id_criterion_e05bb4b9_uniq` (`participant_id`,`criterion_id`,`judge_id`),
  KEY `competition_app_scor_criterion_id_b8dfdfe9_fk_competiti` (`criterion_id`),
  KEY `competition_app_scor_judge_id_695f5293_fk_competiti` (`judge_id`),
  CONSTRAINT `competition_app_scor_criterion_id_b8dfdfe9_fk_competiti` FOREIGN KEY (`criterion_id`) REFERENCES `competition_app_criterion` (`id`),
  CONSTRAINT `competition_app_scor_judge_id_695f5293_fk_competiti` FOREIGN KEY (`judge_id`) REFERENCES `competition_app_judge` (`id`),
  CONSTRAINT `competition_app_scor_participant_id_6f102063_fk_competiti` FOREIGN KEY (`participant_id`) REFERENCES `competition_app_participant` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_score`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_score` WRITE;
/*!40000 ALTER TABLE `competition_app_score` DISABLE KEYS */;
INSERT INTO `competition_app_score` VALUES
(1,20.00,'','2026-11-06 10:00:41.662420','DRAFT',1,1,1),
(2,27.00,'','2026-11-06 10:00:53.831505','SUBMITTED',1,2,1),
(3,36.90,'','2026-11-06 10:01:16.006333','SUBMITTED',2,2,1),
(4,25.90,'','2026-11-06 10:01:16.012546','SUBMITTED',3,2,1),
(5,29.10,'','2026-11-06 10:01:22.228763','SUBMITTED',1,2,2),
(6,27.00,'','2026-11-06 10:01:23.604696','SUBMITTED',1,1,2),
(7,37.30,'','2026-11-06 10:01:36.430118','SUBMITTED',2,2,2),
(8,30.00,'','2026-11-06 10:01:36.434761','SUBMITTED',3,2,2),
(9,36.00,'','2026-11-06 10:01:46.910745','SUBMITTED',2,1,2),
(10,27.00,'','2026-11-06 10:01:46.934326','SUBMITTED',3,1,2);
/*!40000 ALTER TABLE `competition_app_score` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_scorechangelog`
--

DROP TABLE IF EXISTS `competition_app_scorechangelog`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_scorechangelog` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `action` varchar(20) NOT NULL,
  `old_score` decimal(5,2) DEFAULT NULL,
  `new_score` decimal(5,2) DEFAULT NULL,
  `old_status` varchar(20) NOT NULL,
  `new_status` varchar(20) NOT NULL,
  `details` varchar(255) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `changed_by_id` int(11) DEFAULT NULL,
  `competition_id` bigint(20) NOT NULL,
  `criterion_id` bigint(20) DEFAULT NULL,
  `judge_id` bigint(20) DEFAULT NULL,
  `participant_id` bigint(20) NOT NULL,
  `round_id` bigint(20) DEFAULT NULL,
  `score_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `competition_app_scor_changed_by_id_663f3fc7_fk_auth_user` (`changed_by_id`),
  KEY `competition_app_scor_competition_id_4b6836ee_fk_competiti` (`competition_id`),
  KEY `competition_app_scor_criterion_id_24ab3107_fk_competiti` (`criterion_id`),
  KEY `competition_app_scor_judge_id_fd09a84d_fk_competiti` (`judge_id`),
  KEY `competition_app_scor_participant_id_4d84c1c8_fk_competiti` (`participant_id`),
  KEY `competition_app_scor_round_id_60d0659d_fk_competiti` (`round_id`),
  KEY `competition_app_scor_score_id_484d7620_fk_competiti` (`score_id`),
  CONSTRAINT `competition_app_scor_changed_by_id_663f3fc7_fk_auth_user` FOREIGN KEY (`changed_by_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `competition_app_scor_competition_id_4b6836ee_fk_competiti` FOREIGN KEY (`competition_id`) REFERENCES `competition_app_competition` (`id`),
  CONSTRAINT `competition_app_scor_criterion_id_24ab3107_fk_competiti` FOREIGN KEY (`criterion_id`) REFERENCES `competition_app_criterion` (`id`),
  CONSTRAINT `competition_app_scor_judge_id_fd09a84d_fk_competiti` FOREIGN KEY (`judge_id`) REFERENCES `competition_app_judge` (`id`),
  CONSTRAINT `competition_app_scor_participant_id_4d84c1c8_fk_competiti` FOREIGN KEY (`participant_id`) REFERENCES `competition_app_participant` (`id`),
  CONSTRAINT `competition_app_scor_round_id_60d0659d_fk_competiti` FOREIGN KEY (`round_id`) REFERENCES `competition_app_round` (`id`),
  CONSTRAINT `competition_app_scor_score_id_484d7620_fk_competiti` FOREIGN KEY (`score_id`) REFERENCES `competition_app_score` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=67 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_scorechangelog`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_scorechangelog` WRITE;
/*!40000 ALTER TABLE `competition_app_scorechangelog` DISABLE KEYS */;
INSERT INTO `competition_app_scorechangelog` VALUES
(1,'DRAFT_UPDATE',NULL,15.00,'','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:41.666438',4,1,1,1,1,1,1),
(2,'DRAFT_UPDATE',15.00,2.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:41.879887',4,1,1,1,1,1,1),
(3,'DRAFT_UPDATE',2.00,25.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:41.991612',4,1,1,1,1,1,1),
(4,'DRAFT_UPDATE',NULL,1.50,'','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:53.833963',5,1,1,2,1,1,2),
(5,'DRAFT_UPDATE',1.50,7.10,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:54.010305',5,1,1,2,1,1,2),
(6,'DRAFT_UPDATE',7.10,10.50,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:54.156672',5,1,1,2,1,1,2),
(7,'DRAFT_UPDATE',10.50,11.60,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:54.300103',5,1,1,2,1,1,2),
(8,'DRAFT_UPDATE',11.60,13.30,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:54.417035',5,1,1,2,1,1,2),
(9,'DRAFT_UPDATE',13.30,15.20,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:54.555044',5,1,1,2,1,1,2),
(10,'DRAFT_UPDATE',15.20,16.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:54.665967',5,1,1,2,1,1,2),
(11,'DRAFT_UPDATE',16.00,17.20,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:54.780094',5,1,1,2,1,1,2),
(12,'DRAFT_UPDATE',17.20,18.80,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:54.926951',5,1,1,2,1,1,2),
(13,'DRAFT_UPDATE',18.80,20.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:55.080712',5,1,1,2,1,1,2),
(14,'DRAFT_UPDATE',20.00,21.10,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:55.200730',5,1,1,2,1,1,2),
(15,'DRAFT_UPDATE',21.10,22.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:55.370847',5,1,1,2,1,1,2),
(16,'DRAFT_UPDATE',22.00,22.40,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:55.479686',5,1,1,2,1,1,2),
(17,'DRAFT_UPDATE',22.40,22.90,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:55.647144',5,1,1,2,1,1,2),
(18,'DRAFT_UPDATE',22.90,23.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:55.794923',5,1,1,2,1,1,2),
(19,'DRAFT_UPDATE',23.00,23.10,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:55.892243',5,1,1,2,1,1,2),
(20,'DRAFT_UPDATE',23.10,23.20,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:55.985802',5,1,1,2,1,1,2),
(21,'DRAFT_UPDATE',23.20,23.40,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:56.102532',5,1,1,2,1,1,2),
(22,'DRAFT_UPDATE',23.40,23.80,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:56.268423',5,1,1,2,1,1,2),
(23,'DRAFT_UPDATE',23.80,24.20,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:56.414167',5,1,1,2,1,1,2),
(24,'DRAFT_UPDATE',24.20,24.60,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:56.534297',5,1,1,2,1,1,2),
(25,'DRAFT_UPDATE',24.60,24.70,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:56.725374',5,1,1,2,1,1,2),
(26,'DRAFT_UPDATE',24.70,24.80,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:56.997217',5,1,1,2,1,1,2),
(27,'DRAFT_UPDATE',24.80,24.90,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:57.076815',5,1,1,2,1,1,2),
(28,'DRAFT_UPDATE',24.90,25.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:57.175889',5,1,1,2,1,1,2),
(29,'DRAFT_UPDATE',25.00,25.20,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:57.296631',5,1,1,2,1,1,2),
(30,'DRAFT_UPDATE',25.20,25.30,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:57.441338',5,1,1,2,1,1,2),
(31,'DRAFT_UPDATE',25.30,25.40,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:57.927384',5,1,1,2,1,1,2),
(32,'DRAFT_UPDATE',25.40,25.80,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:57.975876',5,1,1,2,1,1,2),
(33,'DRAFT_UPDATE',25.80,26.10,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:58.101110',5,1,1,2,1,1,2),
(34,'DRAFT_UPDATE',26.10,26.20,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:59.044067',5,1,1,2,1,1,2),
(35,'DRAFT_UPDATE',26.20,26.50,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:59.142380',5,1,1,2,1,1,2),
(36,'DRAFT_UPDATE',26.50,26.90,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:59.304346',5,1,1,2,1,1,2),
(37,'DRAFT_UPDATE',26.90,27.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:00:59.425746',5,1,1,2,1,1,2),
(38,'DRAFT_UPDATE',25.00,2.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:00.110194',4,1,1,1,1,1,1),
(39,'DRAFT_UPDATE',2.00,20.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:00.311409',4,1,1,1,1,1,1),
(40,'SUBMITTED',27.00,27.00,'DRAFT','SUBMITTED','LATIN AMERICAN DANCE SPORT - DIRECT SCORING','2026-11-06 10:01:16.001566',5,1,1,2,1,1,2),
(41,'SUBMITTED',NULL,36.90,'','SUBMITTED','LATIN AMERICAN DANCE SPORT - DIRECT SCORING','2026-11-06 10:01:16.007962',5,1,2,2,1,1,3),
(42,'SUBMITTED',NULL,25.90,'','SUBMITTED','LATIN AMERICAN DANCE SPORT - DIRECT SCORING','2026-11-06 10:01:16.014187',5,1,3,2,1,1,4),
(43,'DRAFT_UPDATE',NULL,1.40,'','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:22.231977',5,1,1,2,2,1,5),
(44,'DRAFT_UPDATE',1.40,10.90,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:22.413565',5,1,1,2,2,1,5),
(45,'DRAFT_UPDATE',10.90,18.80,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:22.577322',5,1,1,2,2,1,5),
(46,'DRAFT_UPDATE',18.80,21.70,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:22.714965',5,1,1,2,2,1,5),
(47,'DRAFT_UPDATE',21.70,24.40,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:22.872003',5,1,1,2,2,1,5),
(48,'DRAFT_UPDATE',24.40,28.10,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:23.023336',5,1,1,2,2,1,5),
(49,'DRAFT_UPDATE',28.10,29.10,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:23.153412',5,1,1,2,2,1,5),
(50,'DRAFT_UPDATE',NULL,3.00,'','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:23.616708',4,1,1,1,2,1,6),
(51,'DRAFT_UPDATE',3.00,30.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:24.395075',4,1,1,1,2,1,6),
(52,'DRAFT_UPDATE',30.00,3.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:24.922192',4,1,1,1,2,1,6),
(53,'DRAFT_UPDATE',3.00,0.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:25.073652',4,1,1,1,2,1,6),
(54,'DRAFT_UPDATE',0.00,15.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:25.191620',4,1,1,1,2,1,6),
(55,'DRAFT_UPDATE',15.00,2.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:26.398010',4,1,1,1,2,1,6),
(56,'DRAFT_UPDATE',2.00,25.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:26.590147',4,1,1,1,2,1,6),
(57,'DRAFT_UPDATE',25.00,2.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:27.193058',4,1,1,1,2,1,6),
(58,'DRAFT_UPDATE',2.00,26.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:27.441020',4,1,1,1,2,1,6),
(59,'DRAFT_UPDATE',26.00,2.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:28.596181',4,1,1,1,2,1,6),
(60,'DRAFT_UPDATE',2.00,27.00,'DRAFT','DRAFT','Live draft edit from scoring panel','2026-11-06 10:01:29.363952',4,1,1,1,2,1,6),
(61,'SUBMITTED',29.10,29.10,'DRAFT','SUBMITTED','LATIN AMERICAN DANCE SPORT - DIRECT SCORING','2026-11-06 10:01:36.426744',5,1,1,2,2,1,5),
(62,'SUBMITTED',NULL,37.30,'','SUBMITTED','LATIN AMERICAN DANCE SPORT - DIRECT SCORING','2026-11-06 10:01:36.431403',5,1,2,2,2,1,7),
(63,'SUBMITTED',NULL,30.00,'','SUBMITTED','LATIN AMERICAN DANCE SPORT - DIRECT SCORING','2026-11-06 10:01:36.435681',5,1,3,2,2,1,8),
(64,'SUBMITTED',27.00,27.00,'DRAFT','SUBMITTED','LATIN AMERICAN DANCE SPORT - DIRECT SCORING','2026-11-06 10:01:46.902454',4,1,1,1,2,1,6),
(65,'SUBMITTED',NULL,36.00,'','SUBMITTED','LATIN AMERICAN DANCE SPORT - DIRECT SCORING','2026-11-06 10:01:46.922911',4,1,2,1,2,1,9),
(66,'SUBMITTED',NULL,27.00,'','SUBMITTED','LATIN AMERICAN DANCE SPORT - DIRECT SCORING','2026-11-06 10:01:46.936707',4,1,3,1,2,1,10);
/*!40000 ALTER TABLE `competition_app_scorechangelog` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_sportsevent`
--

DROP TABLE IF EXISTS `competition_app_sportsevent`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_sportsevent` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `category` varchar(20) NOT NULL,
  `gender` varchar(20) NOT NULL,
  `team_based` tinyint(1) NOT NULL,
  `format` varchar(20) NOT NULL,
  `rules` longtext NOT NULL,
  `max_teams` int(10) unsigned DEFAULT NULL CHECK (`max_teams` >= 0),
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `status` varchar(20) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `competition_id` bigint(20) NOT NULL,
  `sport_type_id` bigint(20) NOT NULL,
  `venue_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `competition_app_spor_competition_id_91738173_fk_competiti` (`competition_id`),
  KEY `competition_app_spor_sport_type_id_49914c1b_fk_competiti` (`sport_type_id`),
  KEY `competition_app_spor_venue_id_73110bea_fk_competiti` (`venue_id`),
  CONSTRAINT `competition_app_spor_competition_id_91738173_fk_competiti` FOREIGN KEY (`competition_id`) REFERENCES `competition_app_competition` (`id`),
  CONSTRAINT `competition_app_spor_sport_type_id_49914c1b_fk_competiti` FOREIGN KEY (`sport_type_id`) REFERENCES `competition_app_sporttype` (`id`),
  CONSTRAINT `competition_app_spor_venue_id_73110bea_fk_competiti` FOREIGN KEY (`venue_id`) REFERENCES `competition_app_venue` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_sportsevent`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_sportsevent` WRITE;
/*!40000 ALTER TABLE `competition_app_sportsevent` DISABLE KEYS */;
/*!40000 ALTER TABLE `competition_app_sportsevent` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_sporttype`
--

DROP TABLE IF EXISTS `competition_app_sporttype`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_sporttype` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `description` longtext NOT NULL,
  `team_based` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_sporttype`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_sporttype` WRITE;
/*!40000 ALTER TABLE `competition_app_sporttype` DISABLE KEYS */;
/*!40000 ALTER TABLE `competition_app_sporttype` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `competition_app_venue`
--

DROP TABLE IF EXISTS `competition_app_venue`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_app_venue` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  `location` varchar(200) NOT NULL,
  `capacity` int(10) unsigned DEFAULT NULL CHECK (`capacity` >= 0),
  `description` longtext NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `competition_app_venue`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_app_venue` WRITE;
/*!40000 ALTER TABLE `competition_app_venue` DISABLE KEYS */;
/*!40000 ALTER TABLE `competition_app_venue` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `django_admin_log`
--

DROP TABLE IF EXISTS `django_admin_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_admin_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext DEFAULT NULL,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint(5) unsigned NOT NULL CHECK (`action_flag` >= 0),
  `change_message` longtext NOT NULL,
  `content_type_id` int(11) DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_auth_user_id` (`user_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `django_admin_log_user_id_c564eba6_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_admin_log`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `django_admin_log` WRITE;
/*!40000 ALTER TABLE `django_admin_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `django_admin_log` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `django_content_type`
--

DROP TABLE IF EXISTS `django_content_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_content_type` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=38 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_content_type`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `django_content_type` WRITE;
/*!40000 ALTER TABLE `django_content_type` DISABLE KEYS */;
INSERT INTO `django_content_type` VALUES
(7,'accounts','userprofile'),
(1,'admin','logentry'),
(30,'announcements','announcement'),
(31,'announcements','notification'),
(32,'announcements','notificationpreference'),
(36,'audit','auditlog'),
(2,'auth','group'),
(3,'auth','permission'),
(4,'auth','user'),
(8,'competitions','competition'),
(9,'competitions','criterion'),
(10,'competitions','round'),
(5,'contenttypes','contenttype'),
(29,'eligibility','eligibilityrecord'),
(16,'judges','judge'),
(17,'judges','judgeassignment'),
(11,'participants','participant'),
(12,'participants','participantcompetition'),
(35,'protests','protest'),
(33,'registrations','eventregistration'),
(34,'registrations','registrationtemplate'),
(18,'scoring','award'),
(19,'scoring','awardrecipient'),
(20,'scoring','competitionresult'),
(21,'scoring','score'),
(22,'scoring','scorechangelog'),
(6,'sessions','session'),
(37,'sms','smsmessage'),
(23,'sports','evententry'),
(24,'sports','match'),
(25,'sports','matchentry'),
(26,'sports','sportsevent'),
(27,'sports','sporttype'),
(28,'sports','venue'),
(13,'teams','team'),
(14,'teams','teammembership'),
(15,'teams','teamstaff');
/*!40000 ALTER TABLE `django_content_type` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `django_migrations`
--

DROP TABLE IF EXISTS `django_migrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_migrations` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=53 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_migrations`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `django_migrations` WRITE;
/*!40000 ALTER TABLE `django_migrations` DISABLE KEYS */;
INSERT INTO `django_migrations` VALUES
(1,'contenttypes','0001_initial','2026-10-15 02:30:18.527874'),
(2,'auth','0001_initial','2026-10-15 02:30:18.710999'),
(3,'competitions','0001_initial','2026-10-15 02:30:18.784500'),
(4,'judges','0001_initial','2026-10-15 02:30:18.903838'),
(5,'accounts','0001_initial','2026-10-15 02:30:18.934242'),
(6,'accounts','0002_backfill_user_roles','2026-10-15 02:30:18.950833'),
(7,'accounts','0003_userprofile_middle_name_alter_userprofile_role','2026-10-15 02:30:18.976983'),
(8,'admin','0001_initial','2026-10-15 02:30:19.029297'),
(9,'admin','0002_logentry_remove_auto_add','2026-10-15 02:30:19.037131'),
(10,'admin','0003_logentry_add_action_flag_choices','2026-10-15 02:30:19.045774'),
(11,'announcements','0001_initial','2026-10-15 02:30:19.147207'),
(12,'contenttypes','0002_remove_content_type_name','2026-10-15 02:30:19.201918'),
(13,'audit','0001_initial','2026-10-15 02:30:19.272491'),
(14,'audit','0002_alter_auditlog_action','2026-10-15 02:30:19.280845'),
(15,'auth','0002_alter_permission_name_max_length','2026-10-15 02:30:19.315297'),
(16,'auth','0003_alter_user_email_max_length','2026-10-15 02:30:19.331454'),
(17,'auth','0004_alter_user_username_opts','2026-10-15 02:30:19.341354'),
(18,'auth','0005_alter_user_last_login_null','2026-10-15 02:30:19.364224'),
(19,'auth','0006_require_contenttypes_0002','2026-10-15 02:30:19.365716'),
(20,'auth','0007_alter_validators_add_error_messages','2026-10-15 02:30:19.379026'),
(21,'auth','0008_alter_user_username_max_length','2026-10-15 02:30:19.395559'),
(22,'auth','0009_alter_user_last_name_max_length','2026-10-15 02:30:19.411745'),
(23,'auth','0010_alter_group_name_max_length','2026-10-15 02:30:19.429559'),
(24,'auth','0011_update_proxy_permissions','2026-10-15 02:30:19.440375'),
(25,'auth','0012_alter_user_first_name_max_length','2026-10-15 02:30:19.457322'),
(26,'competitions','0002_competition_bronze_points_and_more','2026-10-15 02:30:19.589675'),
(27,'participants','0001_initial','2026-10-15 02:30:19.664174'),
(28,'participants','0002_participant_identity_and_documents','2026-10-15 02:30:19.911967'),
(29,'eligibility','0001_initial','2026-10-15 02:30:19.977729'),
(30,'teams','0001_initial','2026-10-15 02:30:20.178825'),
(31,'sports','0001_initial','2026-10-15 02:30:20.480095'),
(32,'sports','0002_match_group','2026-10-15 02:30:20.495313'),
(33,'protests','0001_initial','2026-10-15 02:30:20.646208'),
(34,'registrations','0001_initial','2026-10-15 02:30:20.810224'),
(35,'registrations','0002_alter_eventregistration_status','2026-10-15 02:30:20.826351'),
(36,'registrations','0003_remove_eventregistration_unique_registration_sport_event_team_and_more','2026-10-15 02:30:20.960403'),
(37,'scoring','0001_initial','2026-10-15 02:30:21.114739'),
(38,'scoring','0002_recalculate_competition_results','2026-10-15 02:30:21.137383'),
(39,'scoring','0003_award_awardrecipient','2026-10-15 02:30:21.251190'),
(40,'scoring','0004_scorechangelog','2026-10-15 02:30:21.383641'),
(41,'scoring','0005_remove_awardrecipient_unique_award_participant_and_more','2026-10-15 02:30:21.450531'),
(42,'sessions','0001_initial','2026-10-15 02:30:21.463811'),
(43,'sports','0003_remove_evententry_unique_event_team_entry_and_more','2026-10-15 02:30:21.544625'),
(44,'accounts','0004_alter_userprofile_role','2026-10-15 02:39:16.630314'),
(45,'participants','0003_participantcompetition_unique_participant_per_competition','2026-10-15 03:55:34.622322'),
(46,'audit','0003_alter_auditlog_action','2026-10-16 10:09:37.751930'),
(47,'participants','0004_remove_participant_identification_document_and_more','2026-10-16 11:03:10.006515'),
(48,'participants','0005_add_default_identification_number','2026-10-18 09:15:58.030099'),
(49,'registrations','0004_add_registration_templates','2026-10-26 10:32:22.411571'),
(50,'audit','0004_alter_auditlog_action','2026-10-26 10:57:41.417464'),
(51,'announcements','0002_notificationpreference_sms_enabled','2026-11-09 02:37:54.038361'),
(52,'sms','0001_initial','2026-11-09 02:37:54.182875');
/*!40000 ALTER TABLE `django_migrations` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `django_session`
--

DROP TABLE IF EXISTS `django_session`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_session`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `django_session` WRITE;
/*!40000 ALTER TABLE `django_session` DISABLE KEYS */;
INSERT INTO `django_session` VALUES
('3cfx8gdrfzu8usg6vbfmlwldh03uyrh2','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPePE:GBwfst1xNTurS4M5N5h42g4XvdbeVVfpwtDUMKuLuyI','2026-11-21 11:16:20.637760'),
('3s6hsyfz1abo2hd48vyvmn1qc36dak18','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPGWR:78HC2y3ucCI1iPIoqrpb5jUTISVqYqMDwchkysSmXkc','2026-11-20 09:46:11.956791'),
('7elm42vt9ukthfvedsw4hka56a90r8mz','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPebQ:rnE79lgS7cTU3RZUjkjhMyFC_LFhK5G83qzPNnIXXrI','2026-11-21 11:28:56.335393'),
('8qwieumpta1qh4lh0qw0gcyxheqtc2l3','.eJxVjEEOwiAQRe_C2hBCmQFcuvcMZIBBqgaS0q6Md9cmXej2v_f-SwTa1hq2wUuYszgLI06_W6T04LaDfKd26zL1ti5zlLsiDzrktWd-Xg7376DSqN8afSKtPRQFAMaVkpU32VlSKqLCpBnR8uTQFpp0cUzeMhuKjAAMSbw_05Q38g:1xPGiF:ZtBM9KSNz-9fMF7wCHd-oNDCUoEJP8i5zl6fxx1BOpk','2026-11-20 09:58:23.822088'),
('9d5ykllglzwy0u5wkawckhk1artx44z0','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPeYa:QnkVOJLglI089vWyhHdeaq0oSFI_oNAQRSQy1VOxI44','2026-11-21 11:26:00.556615'),
('9daj510s6jxmewlhj2p0gan9lqnsj17y','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPdny:kv_59oJoxAdNfvD5uWns1eBa0s1kONHzjqL4SGFc-uk','2026-11-21 10:37:50.481558'),
('c6f68i8q88s0ysifsg36tai98eeuvhvb','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xQFqy:zMtOiY7C3sZvM8Zpu7vUFKyH6LYNpizIpJ6FtjDjmy0','2026-11-23 03:15:28.461594'),
('jbzavgv5m0kmwlz0f189arybjvzftdkb','.eJxVjEEOwiAQRe_C2hCkwIBL9z0DGWZAqoYmpV0Z765NutDtf-_9l4i4rTVuPS9xYnERVpx-t4T0yG0HfMd2myXNbV2mJHdFHrTLceb8vB7u30HFXr-1szYP2uik0BEAICploFDhgD5pX9Aj2YyaA7B3Q2BgMMmAP3u2ZMX7A-oqOBs:1xPGjh:2MSibzjfp6s64Iwrs_gPEMRLoEnuVE8pE7VKzJbCHn8','2026-11-20 09:59:53.584837'),
('l4piz88pakbltyoehqp1m5s9loexza1u','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPGQf:vnxHzXM6shSMuDlQkUtjXrcKxC1f4HWQ55yIimNmBKE','2026-11-20 09:40:13.593316'),
('ms4rqihef70kc03ad647xqhxoaja0gx5','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPecA:lXStTyXTeR3pt9sH0zf8autLKYHBRQUo1UjhINFWXrY','2026-11-21 11:29:42.087515'),
('n89mqvkly1jyackswewkkvlc9wse0rub','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPdoH:75pKwaw2c6tvSnSc-q-pNu1wfMd9NpyxF-nmjuPxB7A','2026-11-21 10:38:09.761631'),
('pnbvquydyp1d2ogsq8ur97ktys86prpx','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPeZT:a1t0sGvkrqw_Y-ZxRElzvy3_K0ics0CWGD36o1WhwJ4','2026-11-21 11:26:55.600620'),
('qylgayfnqus1fldefy9onusrlu59drjz','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPebv:U45ghLrbgU0PHgEG3ZUhV9TmOc9DsWBBVCPWlhAfaa0','2026-11-21 11:29:27.333996'),
('rmaemsdjs5cc2e1borlmhioet0x8qyrx','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPeab:HDWgflYiTTV7SKmDK5_Q8dhVoA7N7jwdkMDY-60Ytj4','2026-11-21 11:28:05.988856'),
('tbtrftmy2b95z3a38a1bes3csbb2z9kf','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPdku:j4b8lj9MetnP1Pnl17_AOHduky27rDRIzhQs3ODoVJo','2026-11-21 10:34:40.712166'),
('th5nzx8wbfju3aaedy5o2b01vbc9ogvb','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xQFqs:z-PhADVQxLn5evBnQyGYXAzGDi4odbWV4KdBJX1Ut_U','2026-11-23 03:15:22.082673'),
('uu78pydzj2v7zpue2y210x5m7p0bgxy1','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xQFr7:6it38jAciI4bH2_6Om_OS8V3oT7lkStST223bEssci8','2026-11-23 03:15:37.794831'),
('vvlrueak9ehv6f3ww4swmgw8p47jrry8','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPeAw:1-2UT949cL3YWRDliFTDZuCA0xdDy9sbKddYBTHRPCc','2026-11-21 11:01:34.402495'),
('wd1g1r8dg12a6ghdesg7lxd61t56j1eb','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPdlt:2s-S3EjhbhpCY5oyrk7_kBApgzOplc4U8icp-JPufZo','2026-11-21 10:35:41.941305'),
('ynfghps5ucumih1yejzdwx7294j1v7h2','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPdmH:bSJJahAEbJSJDA-Zss0eoGehTYwolvexuGy3PAsnXEQ','2026-11-21 10:36:05.376316'),
('z7e5ygji7r7uj9zcm0q7jr7g72zco5cr','.eJxVjMsOwiAUBf-FtSG9BQq6dN9vIPcBUjU0Ke3K-O_apAvdnpk5LxVxW0vcWlriJOqiQJ1-N0J-pLoDuWO9zZrnui4T6V3RB216nCU9r4f7d1CwlW-NgYMh5-0QAAJlY50YkRyMSdlBx9QPdE7AIQsLAKInIt_11mXL1qn3B-uzOFk:1xPeC1:t-ou9VUHA__jR3u4DGt1tCjlVqBehhLCEeCKrpKFqmA','2026-11-21 11:02:41.377221');
/*!40000 ALTER TABLE `django_session` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `eligibility_eligibilityrecord`
--

DROP TABLE IF EXISTS `eligibility_eligibilityrecord`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `eligibility_eligibilityrecord` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `status` varchar(20) NOT NULL,
  `document` varchar(100) DEFAULT NULL,
  `notes` longtext NOT NULL,
  `submitted_at` datetime(6) NOT NULL,
  `reviewed_at` datetime(6) DEFAULT NULL,
  `competition_id` bigint(20) NOT NULL,
  `participant_id` bigint(20) NOT NULL,
  `reviewed_by_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_eligibility_participant_competition` (`participant_id`,`competition_id`),
  KEY `eligibility_eligibil_competition_id_e2411475_fk_competiti` (`competition_id`),
  KEY `eligibility_eligibil_reviewed_by_id_0e938aff_fk_auth_user` (`reviewed_by_id`),
  CONSTRAINT `eligibility_eligibil_competition_id_e2411475_fk_competiti` FOREIGN KEY (`competition_id`) REFERENCES `competition_app_competition` (`id`),
  CONSTRAINT `eligibility_eligibil_participant_id_7870daf0_fk_competiti` FOREIGN KEY (`participant_id`) REFERENCES `competition_app_participant` (`id`),
  CONSTRAINT `eligibility_eligibil_reviewed_by_id_0e938aff_fk_auth_user` FOREIGN KEY (`reviewed_by_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `eligibility_eligibilityrecord`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `eligibility_eligibilityrecord` WRITE;
/*!40000 ALTER TABLE `eligibility_eligibilityrecord` DISABLE KEYS */;
/*!40000 ALTER TABLE `eligibility_eligibilityrecord` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `registrations_eventregistration`
--

DROP TABLE IF EXISTS `registrations_eventregistration`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `registrations_eventregistration` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `requirements_document` varchar(100) DEFAULT NULL,
  `notes` longtext NOT NULL,
  `status` varchar(20) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `reviewed_at` datetime(6) DEFAULT NULL,
  `competition_id` bigint(20) DEFAULT NULL,
  `participant_id` bigint(20) DEFAULT NULL,
  `registrant_id` int(11) NOT NULL,
  `reviewed_by_id` int(11) DEFAULT NULL,
  `sport_event_id` bigint(20) DEFAULT NULL,
  `team_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_registration_sport_event_team` (`sport_event_id`,`team_id`),
  UNIQUE KEY `unique_registration_sport_event_participant` (`sport_event_id`,`participant_id`),
  UNIQUE KEY `unique_registration_competition_participant` (`competition_id`,`participant_id`),
  KEY `registrations_eventr_participant_id_0467a052_fk_competiti` (`participant_id`),
  KEY `registrations_eventr_registrant_id_2e47a5a1_fk_auth_user` (`registrant_id`),
  KEY `registrations_eventr_reviewed_by_id_ddf243d2_fk_auth_user` (`reviewed_by_id`),
  KEY `registrations_eventr_team_id_53ae0269_fk_teams_tea` (`team_id`),
  CONSTRAINT `registrations_eventr_competition_id_fcd67ee7_fk_competiti` FOREIGN KEY (`competition_id`) REFERENCES `competition_app_competition` (`id`),
  CONSTRAINT `registrations_eventr_participant_id_0467a052_fk_competiti` FOREIGN KEY (`participant_id`) REFERENCES `competition_app_participant` (`id`),
  CONSTRAINT `registrations_eventr_registrant_id_2e47a5a1_fk_auth_user` FOREIGN KEY (`registrant_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `registrations_eventr_reviewed_by_id_ddf243d2_fk_auth_user` FOREIGN KEY (`reviewed_by_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `registrations_eventr_sport_event_id_91510a1e_fk_competiti` FOREIGN KEY (`sport_event_id`) REFERENCES `competition_app_sportsevent` (`id`),
  CONSTRAINT `registrations_eventr_team_id_53ae0269_fk_teams_tea` FOREIGN KEY (`team_id`) REFERENCES `teams_team` (`id`),
  CONSTRAINT `registration_single_contestant` CHECK (`team_id` is not null and `participant_id` is null or `team_id` is null and `participant_id` is not null),
  CONSTRAINT `registration_has_target` CHECK (`competition_id` is not null or `sport_event_id` is not null)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `registrations_eventregistration`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `registrations_eventregistration` WRITE;
/*!40000 ALTER TABLE `registrations_eventregistration` DISABLE KEYS */;
INSERT INTO `registrations_eventregistration` VALUES
(1,'','','APPROVED','2026-11-06 09:54:28.541636','2026-11-06 09:56:15.849780',1,1,2,1,NULL,NULL),
(2,'','','APPROVED','2026-11-06 09:55:48.842559','2026-11-06 09:56:22.384014',1,2,3,1,NULL,NULL);
/*!40000 ALTER TABLE `registrations_eventregistration` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `registrations_registrationtemplate`
--

DROP TABLE IF EXISTS `registrations_registrationtemplate`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `registrations_registrationtemplate` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `description` longtext NOT NULL,
  `requirements_document` varchar(100) DEFAULT NULL,
  `status` varchar(20) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `competition_id` bigint(20) DEFAULT NULL,
  `participant_id` bigint(20) DEFAULT NULL,
  `sport_event_id` bigint(20) DEFAULT NULL,
  `team_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `registrations_regist_competition_id_2ffa140e_fk_competiti` (`competition_id`),
  KEY `registrations_regist_participant_id_3bf9e168_fk_competiti` (`participant_id`),
  KEY `registrations_regist_sport_event_id_dce28a3d_fk_competiti` (`sport_event_id`),
  KEY `registrations_regist_team_id_5ee9fe25_fk_teams_tea` (`team_id`),
  CONSTRAINT `registrations_regist_competition_id_2ffa140e_fk_competiti` FOREIGN KEY (`competition_id`) REFERENCES `competition_app_competition` (`id`),
  CONSTRAINT `registrations_regist_participant_id_3bf9e168_fk_competiti` FOREIGN KEY (`participant_id`) REFERENCES `competition_app_participant` (`id`),
  CONSTRAINT `registrations_regist_sport_event_id_dce28a3d_fk_competiti` FOREIGN KEY (`sport_event_id`) REFERENCES `competition_app_sportsevent` (`id`),
  CONSTRAINT `registrations_regist_team_id_5ee9fe25_fk_teams_tea` FOREIGN KEY (`team_id`) REFERENCES `teams_team` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `registrations_registrationtemplate`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `registrations_registrationtemplate` WRITE;
/*!40000 ALTER TABLE `registrations_registrationtemplate` DISABLE KEYS */;
/*!40000 ALTER TABLE `registrations_registrationtemplate` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `sms_smsmessage`
--

DROP TABLE IF EXISTS `sms_smsmessage`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `sms_smsmessage` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `recipient` varchar(20) NOT NULL,
  `recipient_name` varchar(150) NOT NULL,
  `body` longtext NOT NULL,
  `sender_name` varchar(40) NOT NULL,
  `category` varchar(20) NOT NULL,
  `status` varchar(10) NOT NULL,
  `semaphore_message_id` bigint(20) DEFAULT NULL,
  `provider_status` varchar(30) NOT NULL,
  `error` longtext NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `created_by_id` int(11) DEFAULT NULL,
  `match_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `sms_smsmessage_created_by_id_926272e5_fk_auth_user_id` (`created_by_id`),
  KEY `sms_smsmessage_match_id_c9e28a5f_fk_competition_app_match_id` (`match_id`),
  KEY `sms_smsmessage_recipient_7176e6b2` (`recipient`),
  KEY `sms_smsmessage_semaphore_message_id_d7cc6d2a` (`semaphore_message_id`),
  KEY `sms_smsmess_status_4ce5a4_idx` (`status`),
  KEY `sms_smsmess_categor_b51cfe_idx` (`category`),
  KEY `sms_smsmess_created_84350a_idx` (`created_at`),
  CONSTRAINT `sms_smsmessage_created_by_id_926272e5_fk_auth_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `sms_smsmessage_match_id_c9e28a5f_fk_competition_app_match_id` FOREIGN KEY (`match_id`) REFERENCES `competition_app_match` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sms_smsmessage`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `sms_smsmessage` WRITE;
/*!40000 ALTER TABLE `sms_smsmessage` DISABLE KEYS */;
INSERT INTO `sms_smsmessage` VALUES
(1,'09456922740','Owner','Competrack test: SMS notifications are working. This is a system test message.','Competrack','MANUAL','SENT',284490355,'Pending','','2026-11-09 02:53:11.154069',NULL,NULL),
(2,'09456922740','Owner','Competrack delivery test 2 sent at 10:54 AM. If you can read this, receiving works.','Competrack','MANUAL','SENT',284490536,'Pending','','2026-11-09 02:54:08.030222',NULL,NULL),
(3,'09456922740','Owner','[Competrack] LATIN AMERICAN DANCE SPORT update: SMS notifications are now active. Match schedules, reminders, live updates, and results will be sent here. Sample test only - no action needed.','Competrack','TEST','SENT',284490684,'Pending','','2026-11-09 02:55:54.347313',NULL,NULL);
/*!40000 ALTER TABLE `sms_smsmessage` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `teams_team`
--

DROP TABLE IF EXISTS `teams_team`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `teams_team` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `code` varchar(20) NOT NULL,
  `name` varchar(150) NOT NULL,
  `category` varchar(20) NOT NULL,
  `description` longtext NOT NULL,
  `logo` varchar(100) DEFAULT NULL,
  `status` varchar(20) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `created_by_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  UNIQUE KEY `name` (`name`),
  KEY `teams_team_created_by_id_4d452be8_fk_auth_user_id` (`created_by_id`),
  CONSTRAINT `teams_team_created_by_id_4d452be8_fk_auth_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `teams_team`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `teams_team` WRITE;
/*!40000 ALTER TABLE `teams_team` DISABLE KEYS */;
INSERT INTO `teams_team` VALUES
(1,'TEAM-0B4F7BEA','Team Red','CULTURAL','','','APPROVED','2026-11-06 09:48:23.923676','2026-11-06 09:49:19.633502',1),
(2,'TEAM-2EC28083','Team Blue','CULTURAL','','','APPROVED','2026-11-06 09:48:41.153789','2026-11-06 09:49:05.683201',1);
/*!40000 ALTER TABLE `teams_team` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `teams_teammembership`
--

DROP TABLE IF EXISTS `teams_teammembership`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `teams_teammembership` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `member_number` int(10) unsigned DEFAULT NULL CHECK (`member_number` >= 0),
  `status` varchar(20) NOT NULL,
  `joined_at` datetime(6) NOT NULL,
  `participant_id` bigint(20) NOT NULL,
  `team_id` bigint(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `participant_id` (`participant_id`),
  UNIQUE KEY `unique_team_member_number` (`team_id`,`member_number`),
  CONSTRAINT `teams_teammembership_participant_id_c0651ba3_fk_competiti` FOREIGN KEY (`participant_id`) REFERENCES `competition_app_participant` (`id`),
  CONSTRAINT `teams_teammembership_team_id_2ee7a456_fk_teams_team_id` FOREIGN KEY (`team_id`) REFERENCES `teams_team` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `teams_teammembership`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `teams_teammembership` WRITE;
/*!40000 ALTER TABLE `teams_teammembership` DISABLE KEYS */;
INSERT INTO `teams_teammembership` VALUES
(1,NULL,'ACTIVE','2026-11-06 09:53:20.254265',1,2),
(2,NULL,'ACTIVE','2026-11-06 09:54:52.359300',2,1);
/*!40000 ALTER TABLE `teams_teammembership` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `teams_teamstaff`
--

DROP TABLE IF EXISTS `teams_teamstaff`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `teams_teamstaff` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `role` varchar(20) NOT NULL,
  `assigned_at` datetime(6) NOT NULL,
  `team_id` bigint(20) NOT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_team_staff_role` (`team_id`,`user_id`,`role`),
  KEY `teams_teamstaff_user_id_14fe967b_fk_auth_user_id` (`user_id`),
  CONSTRAINT `teams_teamstaff_team_id_1ac63737_fk_teams_team_id` FOREIGN KEY (`team_id`) REFERENCES `teams_team` (`id`),
  CONSTRAINT `teams_teamstaff_user_id_14fe967b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `teams_teamstaff`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `teams_teamstaff` WRITE;
/*!40000 ALTER TABLE `teams_teamstaff` DISABLE KEYS */;
/*!40000 ALTER TABLE `teams_teamstaff` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*M!100616 SET NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY */;

-- Dump completed on 2026-11-13 17:35:54
